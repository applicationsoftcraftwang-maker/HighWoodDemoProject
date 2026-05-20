import { useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { api, ApiError } from '../lib/api';

type EmissionUnit = 'kg' | 'tonnes' | 'lbs';

interface ReadingRow {
  value: string;
  unit: EmissionUnit;
  captured_at: string;
}

interface Props {
  siteId: string;
  onSuccess: () => void;
}

const nowLocal = () =>
  new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);

type ResultType = 'success' | 'duplicate' | 'conflict' | 'error';

const RESULT_LABEL: Record<ResultType, string> = {
  success: 'Success',
  duplicate: 'Duplicate replay',
  conflict: 'Ingestion token conflict',
  error: 'Request failed',
};

export function IngestForm({ siteId, onSuccess }: Props) {
  const [rows, setRows] = useState<ReadingRow[]>([
    { value: '', unit: 'kg', captured_at: nowLocal() },
  ]);

  const [ingestionToken, setIngestionToken] = useState(uuidv4());
  const [loading, setLoading] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [result, setResult] = useState<{ type: ResultType; message: string } | null>(null);

  const addRow = () =>
    setRows((currentRows) =>
      currentRows.length < 100
        ? [...currentRows, { value: '', unit: 'kg', captured_at: nowLocal() }]
        : currentRows,
    );

  const removeRow = (index: number) =>
    setRows((currentRows) => currentRows.filter((_, rowIndex) => rowIndex !== index));

  const update = (index: number, key: keyof ReadingRow, value: string) =>
    setRows((currentRows) =>
      currentRows.map((row, rowIndex) =>
        rowIndex === index ? { ...row, [key]: value } : row,
      ),
    );

  const submit = async (useNewToken = false) => {
    const token = useNewToken ? uuidv4() : ingestionToken;

    if (useNewToken) {
      setIngestionToken(token);
      setRetryCount(0);
    }

    if (!siteId) {
      setResult({
        type: 'error',
        message: 'Please select a monitoring site before submitting readings.',
      });
      return;
    }

    const invalid = rows.some((row) => {
      const numericValue = Number(row.value);
      return (
        row.value.trim() === '' ||
        Number.isNaN(numericValue) ||
        numericValue < 0 ||
        !row.captured_at
      );
    });

    if (invalid) {
      setResult({
        type: 'error',
        message: 'Please enter a valid non-negative value and timestamp for every reading.',
      });
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const data = await api.ingest.batch({
        site_id: siteId,
        ingestion_token: token,
        trace_request_id: `ui-${token}`,
        readings: rows.map((row) => ({
          emission_value: Number(row.value),
          emission_unit: row.unit,
          captured_at: new Date(row.captured_at).toISOString(),
        })),
      });

      setResult({
        type: data.status === 'duplicate' ? 'duplicate' : 'success',
        message: data.message ?? 'Batch submitted successfully.',
      });

      if (data.status !== 'duplicate') {
        onSuccess();
      }
    } catch (e) {
      if (
        e instanceof ApiError &&
        (
          e.code === 'INGESTION_TOKEN_REUSED_WITH_DIFFERENT_PAYLOAD' ||
          e.code === 'IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD'
        )
      ) {
        setResult({
          type: 'conflict',
          message:
            'This ingestion token was already used for a different request. Generate a new key before resubmitting.',
        });
      } else {
        setResult({
          type: 'error',
          message: e instanceof ApiError ? e.message : String(e),
        });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ingest-card card">
      <div className="card-header">
        <div>
          <h2 className="card-title">Manual Ingestion</h2>
          <p className="card-subtitle">
            Submit one or more methane readings for this site.
          </p>
        </div>

        <span className="pill">
          Key {ingestionToken.slice(0, 8)}… · {rows.length}/100
        </span>
      </div>

      <div className="form-body">
        <div className="form-row-list">
          {rows.map((row, index) => (
            <div key={index} className="input-grid">
              <input
                className="input"
                type="number"
                min="0"
                placeholder="Emission value"
                value={row.value}
                onChange={(event) => update(index, 'value', event.target.value)}
              />

              <select
                className="select"
                value={row.unit}
                onChange={(event) => update(index, 'unit', event.target.value as EmissionUnit)}
              >
                <option value="kg">kg</option>
                <option value="tonnes">tonnes</option>
                <option value="lbs">lbs</option>
              </select>

              <input
                className="input"
                type="datetime-local"
                value={row.captured_at}
                onChange={(event) => update(index, 'captured_at', event.target.value)}
              />

              {rows.length > 1 ? (
                <button
                  className="icon-btn"
                  onClick={() => removeRow(index)}
                  aria-label="Remove reading"
                  type="button"
                >
                  ×
                </button>
              ) : (
                <div />
              )}
            </div>
          ))}
        </div>

        <div className="form-actions">
          <button
            className="secondary-btn"
            onClick={addRow}
            disabled={rows.length >= 100 || loading}
            type="button"
          >
            + Add Row
          </button>

          <button
            className="primary-btn"
            style={{ flex: 1 }}
            onClick={() => submit(false)}
            disabled={loading}
            type="button"
          >
            {loading
              ? 'Submitting…'
              : `Submit Batch · ${rows.length} Reading${rows.length !== 1 ? 's' : ''}`}
          </button>
        </div>

        {result && (
          <div className={`form-result ${result.type}`}>
            <span>
              <strong>{RESULT_LABEL[result.type]}:</strong> {result.message}
            </span>

            {(result.type === 'error' || result.type === 'conflict') && (
              <span style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                {result.type === 'error' && (
                  <button
                    className="secondary-btn"
                    onClick={() => {
                      setRetryCount((count) => count + 1);
                      submit(false);
                    }}
                    type="button"
                  >
                    Retry ({retryCount})
                  </button>
                )}

                <button
                  className="secondary-btn"
                  onClick={() => submit(true)}
                  type="button"
                >
                  New Key
                </button>
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}