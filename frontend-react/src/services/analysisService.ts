import { apiClient } from './api';
import { Analysis, PaginatedAnalyses, TriggerRCAPayload } from '../types/analysis';

export const analysisService = {
  async triggerRCA(incidentId: string, payload: TriggerRCAPayload = {}): Promise<Analysis> {
    const cleanPayload: Record<string, string | number> = {};
    if (payload.additional_context) cleanPayload.additional_context = payload.additional_context;
    if (payload.max_evidence_logs) cleanPayload.max_evidence_logs = payload.max_evidence_logs;

    const response = await apiClient.post<Analysis>(`/incidents/${incidentId}/analyze`, cleanPayload);
    return response.data;
  },

  async getIncidentAnalyses(incidentId: string): Promise<PaginatedAnalyses> {
    const response = await apiClient.get<PaginatedAnalyses>(`/incidents/${incidentId}/analyses`);
    return response.data;
  },
};
