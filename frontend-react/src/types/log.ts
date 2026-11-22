export interface LogEntry {
  id: string;
  log_id: string;
  user_id: string;
  timestamp: string;
  service_name: string;
  environment: string;
  level: string;
  message: string;
  source?: string | null;
  host?: string | null;
  error_signature?: string | null;
  created_at: string;
}

export interface PaginatedLogs {
  items: LogEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface IngestLogPayload {
  service_name: string;
  environment: string;
  level: string;
  message: string;
  source?: string;
  host?: string;
  timestamp?: string;
}

export interface BatchLogIngestPayload {
  logs: IngestLogPayload[];
}

export interface BatchLogIngestResponse {
  successful_count: number;
  failed_count: number;
  incident_triggered: boolean;
  incident_id?: string | null;
}
