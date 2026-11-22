export interface HistoricalAnalysisSummary {
  analysis_id: string;
  probable_root_cause: string;
  confidence_level: string;
}

export interface KnowledgeDocument {
  id: string;
  knowledge_id: string;
  source_incident_id: string;
  user_id: string;
  service_name: string;
  environment: string;
  error_signature: string;
  title: string;
  description: string;
  diagnostic_summary: string;
  confirmed_resolution?: string | null;
  has_verified_resolution: boolean;
  score?: number;
  historical_analysis?: HistoricalAnalysisSummary | null;
  created_at: string;
}

export interface KnowledgeSearchPayload {
  query: string;
  service_name?: string | null;
  environment?: string | null;
  top_k?: number;
  min_similarity?: number;
}

export interface KnowledgeSearchResponse {
  results: KnowledgeDocument[];
  total: number;
}
