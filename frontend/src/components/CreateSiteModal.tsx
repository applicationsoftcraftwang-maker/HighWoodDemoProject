import React, { useEffect, useRef, useState } from 'react';
import { z } from 'zod';
import { api, ApiError } from '../lib/api';

const CreateSiteSchema = z.object({
  site_name: z.string().min(1, 'Site name required').max(255),
  site_location: z.string().min(1, 'Location required').max(255),
  methane_emission_limit: z.number().positive('Must be greater than 0'),
});

type CreateSiteForm = {
  site_name: string;
  site_location: string;
  methane_emission_limit: string;
};

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

export function CreateSiteModal({ onClose, onCreated }: Props) {
  const [form, setForm] = useState<CreateSiteForm>({
    site_name: '',
    site_location: '',
    methane_emission_limit: '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const siteNameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    siteNameRef.current?.focus();
  }, []);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  const updateForm = (key: keyof CreateSiteForm, value: string) => {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));

    setErrors((current) => ({
      ...current,
      [key]: '',
    }));

    setApiError(null);
  };

  const submit = async () => {
    setApiError(null);

    const parsed = CreateSiteSchema.safeParse({
      site_name: form.site_name.trim(),
      site_location: form.site_location.trim(),
      methane_emission_limit: form.methane_emission_limit
        ? Number(form.methane_emission_limit)
        : undefined,
    });

    if (!parsed.success) {
      const fieldErrors: Record<string, string> = {};

      parsed.error.issues.forEach((issue) => {
        const fieldName = issue.path[0] as string;
        fieldErrors[fieldName] = issue.message;
      });

      setErrors(fieldErrors);
      return;
    }

    setErrors({});
    setLoading(true);

    try {
      await api.sites.create({
        site_name: parsed.data.site_name,
        site_location: parsed.data.site_location,
        methane_emission_limit: parsed.data.methane_emission_limit,
        site_metadata: {
          source: 'manual_ui',
        },
      });

      onCreated();
      onClose();
    } catch (error) {
      setApiError(error instanceof ApiError ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  const fields: {
    label: string;
    key: keyof CreateSiteForm;
    placeholder: string;
    type: string;
  }[] = [
    {
      label: 'Site name',
      key: 'site_name',
      placeholder: 'Highwood Well Pad Alpha',
      type: 'text',
    },
    {
      label: 'Location',
      key: 'site_location',
      placeholder: 'Alberta, Canada',
      type: 'text',
    },
    {
      label: 'Emission limit (kg)',
      key: 'methane_emission_limit',
      placeholder: '5000',
      type: 'number',
    },
  ];

  return (
    <div
      className="modal-backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="modal">
        <div className="card-header">
          <div>
            <h2 className="card-title">New Monitoring Site</h2>
            <p className="card-subtitle">
              Configure a facility for methane emissions tracking.
            </p>
          </div>

          <button
            className="secondary-btn"
            onClick={onClose}
            type="button"
            disabled={loading}
          >
            ×
          </button>
        </div>

        <div className="modal-body">
          {fields.map(({ label, key, placeholder, type }) => (
            <div className="field" key={key}>
              <label className="label">{label}</label>

              <input
                ref={key === 'site_name' ? siteNameRef : undefined}
                className="input"
                type={type}
                min={type === 'number' ? '0' : undefined}
                step={type === 'number' ? '0.01' : undefined}
                placeholder={placeholder}
                value={form[key]}
                onChange={(event) => updateForm(key, event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    submit();
                  }
                }}
                disabled={loading}
              />

              {errors[key] ? (
                <div className="field-error">{errors[key]}</div>
              ) : null}
            </div>
          ))}

          {apiError ? (
            <div className="form-result error">
              <strong>Request failed:</strong> {apiError}
            </div>
          ) : null}

          <div className="form-actions">
            <button
              className="secondary-btn"
              style={{ flex: 1 }}
              onClick={onClose}
              type="button"
              disabled={loading}
            >
              Cancel
            </button>

            <button
              className="primary-btn"
              style={{ flex: 2 }}
              onClick={submit}
              disabled={loading}
              type="button"
            >
              {loading ? 'Creating…' : 'Create Site'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}