import { apiClient } from './api';
import {
  BatchLogIngestPayload,
  BatchLogIngestResponse,
  IngestLogPayload,
  LogEntry,
  PaginatedLogs,
} from '../types/log';

export const logService = {
  async ingestSingleLog(payload: IngestLogPayload): Promise<LogEntry> {
    const response = await apiClient.post<LogEntry>('/logs/ingest', payload);
    return response.data;
  },

  async ingestBatchLogs(payload: BatchLogIngestPayload): Promise<BatchLogIngestResponse> {
    const response = await apiClient.post<BatchLogIngestResponse>('/logs/ingest/batch', payload);
    return response.data;
  },

  async listLogs(params: {
    service_name?: string;
    environment?: string;
    level?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<PaginatedLogs> {
    const cleanParams: Record<string, string | number> = {
      limit: params.limit || 50,
      offset: params.offset || 0,
    };
    if (params.service_name && params.service_name !== 'ALL') cleanParams.service_name = params.service_name;
    if (params.environment && params.environment !== 'ALL') cleanParams.environment = params.environment;
    if (params.level && params.level !== 'ALL') cleanParams.level = params.level;

    const response = await apiClient.get<PaginatedLogs>('/logs', { params: cleanParams });
    return response.data;
  },

  async getLog(logId: string): Promise<LogEntry> {
    const response = await apiClient.get<LogEntry>(`/logs/${logId}`);
    return response.data;
  },
};
