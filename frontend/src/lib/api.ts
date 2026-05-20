import type {
  Site,
  SiteMetrics,
  IngestBatchRequest,
  IngestResult,
  IngestStats,
} from '../types';

const BASE =
  (import.meta as any).env?.VITE_API_URL ?? 'http://localhost:8000/api/v1';

const TENANT_ID =
  (import.meta as any).env?.VITE_TENANT_ID ??
  '00000000-0000-0000-0000-000000000001';

export class ApiError {
  name = 'ApiError';

  constructor(
    public code: string,
    public message: string,
    public details?: unknown,
    public status?: number,
  ) {}
}

export interface CreateSiteRequest {
  site_name: string;
  site_location: string;
  methane_emission_limit: number;
  site_metadata?: Record<string, unknown>;
}

type ApiEnvelope<T> =
  | {
      success: true;
      data: T;
      meta?: unknown;
    }
  | {
      success: false;
      error?: {
        code?: string;
        message?: string;
        details?: unknown;
      };
      meta?: unknown;
    };

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-Id': TENANT_ID,
      ...(options?.headers ?? {}),
    },
  });

  let json: ApiEnvelope<T>;

  try {
    json = await response.json();
  } catch {
    throw new ApiError(
      'INVALID_RESPONSE',
      'The server returned an invalid response.',
      undefined,
      response.status,
    );
  }

  if (!response.ok || !json.success) {
    throw new ApiError(
      json.success === false ? json.error?.code ?? 'UNKNOWN' : 'HTTP_ERROR',
      json.success === false
        ? json.error?.message ?? 'API error'
        : `HTTP request failed with status ${response.status}`,
      json.success === false ? json.error?.details : undefined,
      response.status,
    );
  }

  return json.data;
}

export const api = {
  sites: {
    list: () => req<Site[]>('/sites'),

    create: (body: CreateSiteRequest) =>
      req<Site>('/sites', {
        method: 'POST',
        body: JSON.stringify(body),
      }),

    get: (siteId: string) => req<Site>(`/sites/${siteId}`),

    metrics: (siteId: string) => req<SiteMetrics>(`/sites/${siteId}/metrics`),
  },

  ingest: {
    batch: (body: IngestBatchRequest) =>
      req<IngestResult>('/ingest', {
        method: 'POST',
        body: JSON.stringify(body),
      }),

    stats: () => req<IngestStats>('/ingest/stats'),
  },
};