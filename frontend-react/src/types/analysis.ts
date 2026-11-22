export type ConfidenceLevel = 'LOW' | 'MEDIUM' | 'HIGH';

export interface SimilarIncidentReference {
  knowledge_id: string;
  source_incident_id: string;
  similarity_score: number;
  service_name: string;
  environment: string;
  title: string;
  has_verified_resolution: boolean;
  confirmed_resolution?: string | null;
  probable_root_cause?: string | null;
}

export interface Analysis {
  id: string;
  analysis_id: string;
  incident_id: string;
  user_id: string;
  probable_root_cause: string;
  explanation: string;
  supporting_evidence: string[];
  contributing_factors: string[];
  confidence_level: ConfidenceLevel;
  recommended_actions: string[];
  limitations: string[];
  provider: string;
  model: string;
  evidence_log_count: number;
  redacted_secrets_count: number;
  rag_status: string;
  similar_incidents: SimilarIncidentReference[];
  created_at: string;
}

export interface PaginatedAnalyses {
  items: Analysis[];
  total: number;
  limit: number;
  offset: number;
}

export interface TriggerRCAPayload {
  additional_context?: string;
  max_evidence_logs?: number;
}
