export interface DailyTrend {
  date: string;
  count: number;
}

export interface RecurringPattern {
  error_signature: string;
  title: string;
  service_name: string;
  severity: string;
  count: number;
}

export interface AnalyticsOverview {
  total_incidents: number;
  open_incidents: number;
  acknowledged_incidents: number;
  resolved_incidents: number;
  critical_incidents: number;
  resolution_rate_pct: number;
  mtta_minutes?: number | null;
  mttr_minutes?: number | null;
  daily_trends: DailyTrend[];
  by_severity: Record<string, number>;
  by_service: Record<string, number>;
  by_status: Record<string, number>;
  by_environment: Record<string, number>;
  recurring_patterns?: RecurringPattern[];
}
