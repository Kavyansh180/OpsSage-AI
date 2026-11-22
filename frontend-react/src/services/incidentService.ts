import { apiClient } from './api';
import {
  AssignIncidentPayload,
  Incident,
  IncidentFilterParams,
  IncidentHistoryResponse,
  InvestigationNote,
  PaginatedIncidents,
  RecordResolutionPayload,
  UpdateSeverityPayload,
} from '../types/incident';

export const incidentService = {
  async listIncidents(params: IncidentFilterParams = {}): Promise<PaginatedIncidents> {
    const cleanParams: Record<string, string | number> = {
      limit: params.limit || 50,
      offset: params.offset || 0,
    };
    if (params.status && params.status !== 'ALL') cleanParams.status = params.status;
    if (params.severity && params.severity !== 'ALL') cleanParams.severity = params.severity;
    if (params.service_name && params.service_name !== 'ALL') cleanParams.service_name = params.service_name;
    if (params.environment && params.environment !== 'ALL') cleanParams.environment = params.environment;

    const response = await apiClient.get<PaginatedIncidents>('/incidents', { params: cleanParams });
    return response.data;
  },

  async getIncident(incidentId: string): Promise<Incident> {
    const response = await apiClient.get<Incident>(`/incidents/${incidentId}`);
    return response.data;
  },

  async acknowledgeIncident(incidentId: string): Promise<Incident> {
    const response = await apiClient.patch<Incident>(`/incidents/${incidentId}/acknowledge`);
    return response.data;
  },

  async assignIncident(incidentId: string, payload: AssignIncidentPayload): Promise<Incident> {
    const response = await apiClient.patch<Incident>(`/incidents/${incidentId}/assign`, payload);
    return response.data;
  },

  async updateSeverity(incidentId: string, payload: UpdateSeverityPayload): Promise<Incident> {
    const response = await apiClient.patch<Incident>(`/incidents/${incidentId}/severity`, payload);
    return response.data;
  },

  async addNote(incidentId: string, note: string): Promise<InvestigationNote> {
    const response = await apiClient.post<InvestigationNote>(`/incidents/${incidentId}/notes`, { note });
    return response.data;
  },

  async recordResolution(incidentId: string, payload: RecordResolutionPayload): Promise<Incident> {
    const response = await apiClient.post<Incident>(`/incidents/${incidentId}/resolve`, payload);
    return response.data;
  },

  async verifyResolution(incidentId: string, isVerified: boolean = true, notes?: string): Promise<Incident> {
    const response = await apiClient.post<Incident>(`/incidents/${incidentId}/verify-resolution`, {
      is_verified: isVerified,
      verification_notes: notes,
    });
    return response.data;
  },

  async getIncidentHistory(incidentId: string): Promise<IncidentHistoryResponse> {
    const response = await apiClient.get<IncidentHistoryResponse>(`/incidents/${incidentId}/history`);
    return response.data;
  },
};
