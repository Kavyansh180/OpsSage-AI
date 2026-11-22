import { apiClient } from './api';
import {
  KnowledgeDocument,
  KnowledgeSearchPayload,
  KnowledgeSearchResponse,
} from '../types/knowledge';

export const knowledgeService = {
  async searchKnowledge(payload: KnowledgeSearchPayload): Promise<KnowledgeSearchResponse> {
    const cleanPayload: Record<string, string | number> = {
      query: payload.query.trim(),
      top_k: payload.top_k || 5,
      min_similarity: payload.min_similarity !== undefined ? payload.min_similarity : 0.5,
    };
    if (payload.service_name && payload.service_name !== 'ALL') {
      cleanPayload.service_name = payload.service_name;
    }
    if (payload.environment && payload.environment !== 'ALL') {
      cleanPayload.environment = payload.environment;
    }

    const response = await apiClient.post<KnowledgeSearchResponse>('/knowledge/search', cleanPayload);
    return response.data;
  },

  async getKnowledgeDocument(knowledgeId: string): Promise<KnowledgeDocument> {
    const response = await apiClient.get<KnowledgeDocument>(`/knowledge/${knowledgeId}`);
    return response.data;
  },
};
