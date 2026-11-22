import { apiClient } from './api';
import { AnalyticsOverview } from '../types/analytics';

export const analyticsService = {
  async getOverview(days: number = 30): Promise<AnalyticsOverview> {
    const response = await apiClient.get<AnalyticsOverview>('/analytics/overview', {
      params: { days },
    });
    return response.data;
  },
};
