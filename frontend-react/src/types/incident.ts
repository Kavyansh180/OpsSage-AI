export type IncidentSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type IncidentStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';

export interface InvestigationNote {
  note_id: string;
  user_id: string;
  user_email: string;
  note: string;
  created_at: string;
}

export interface Incident {
  id: string;
  incident_id: string;
  user_id: string;
  environment: string;
  service_name: string;
  error_signature: string;
  title: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  first_seen: string;
  last_seen: string;
  window_event_count: number;
  event_count: number;
  related_log_ids: string[];
  created_at: string;
  updated_at: string;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
  assigned_to?: string | null;
  assigned_at?: string | null;
  assigned_by?: string | null;
  investigation_notes: InvestigationNote[];
  confirmed_root_cause?: string | null;
  confirmed_resolution?: string | null;
  resolution_actions: string[];
  has_verified_resolution: boolean;
  verified_at?: string | null;
  verified_by?: string | null;
  rca_analysis_id?: string | null;
  resolved_at?: string | null;
  resolved_by?: string | null;
  knowledge_synced: boolean;
  knowledge_synced_at?: string | null;
}

export interface PaginatedIncidents {
  items: Incident[];
  total: number;
  limit: number;
  offset: number;
}

export interface IncidentFilterParams {
  status?: string;
  severity?: string;
  service_name?: string;
  environment?: string;
  limit?: number;
  offset?: number;
}

export interface AssignIncidentPayload {
  assigned_to: string;
}

export interface UpdateSeverityPayload {
  severity: IncidentSeverity;
}

export interface RecordResolutionPayload {
  confirmed_root_cause: string;
  confirmed_resolution: string;
  resolution_actions?: string[];
  is_verified?: boolean;
  rca_analysis_id?: string | null;
  notes?: string | null;
}

export interface AuditHistoryEntry {
  timestamp: string;
  action: string;
  actor_email: string;
  details: string | Record<string, any>;
  incident_id: string;
}

export interface IncidentHistoryResponse {
  items: AuditHistoryEntry[];
  total: number;
}
