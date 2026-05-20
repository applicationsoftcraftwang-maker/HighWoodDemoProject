export interface Site {
  site_id: string;
  customer_id: string;
  site_name: string;
  site_location: string;
  methane_emission_limit: number;
  methane_accumulated_emissions_to_date: number;
  site_metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface SiteMetrics {
  site_id: string;
  site_name: string;
  emission_limit: number;
  total_emissions_to_date: number;
  compliance_status: 'within_limit' | 'limit_exceeded';
  utilization_percent: number;
  measurement_count: number;
  last_measurement_at: string | null;
}

export interface ReadingItem {
  emission_value: number;
  emission_unit: 'kg' | 'tonnes' | 'lbs';
  captured_at: string;
}

export interface IngestBatchRequest {
  site_id: string;
  ingestion_token: string;
  trace_request_id: string;
  readings: ReadingItem[];
}

export interface IngestResult {
  ingestion_job_id: string;
  ingestion_token: string;
  trace_request_id?: string;
  status: 'processed' | 'duplicate' | 'conflict' | 'failed';
  received_record_count?: number;
  processed_record_count?: number;
  message: string;
}

export interface IngestStats {
  total_emissions_to_date: number;
  emission_limit: number;
  total_measurements: number;
  active_sites: number;
}