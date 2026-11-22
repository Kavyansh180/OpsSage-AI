import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertOctagon,
  CheckCircle2,
  AlertTriangle,
  Clock,
  TrendingUp,
  Layers,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { analyticsService } from '../services/analyticsService';
import { incidentService } from '../services/incidentService';
import { AnalyticsOverview } from '../types/analytics';
import { Incident } from '../types/incident';
import { MetricCard } from '../components/common/MetricCard';
import { SeverityBadge } from '../components/common/SeverityBadge';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorBanner } from '../components/common/ErrorBanner';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [recentIncidents, setRecentIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setError(null);
    try {
      const [overviewData, incidentsData] = await Promise.all([
        analyticsService.getOverview(30),
        incidentService.listIncidents({ limit: 5 }),
      ]);
      setAnalytics(overviewData);
      setRecentIncidents(incidentsData.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch dashboard data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  if (loading) {
    return <LoadingSpinner label="Loading telemetry & metrics..." />;
  }

  // Format data for charts
  const severityData = Object.entries(analytics?.by_severity || {}).map(([key, val]) => ({
    severity: key,
    count: val,
  }));

  const serviceData = Object.entries(analytics?.by_service || {}).map(([key, val]) => ({
    service: key,
    count: val,
  }));

  const statusData = Object.entries(analytics?.by_status || {}).map(([key, val]) => ({
    status: key,
    count: val,
  }));

  return (
    <div className="space-y-6">
      {/* Top Banner & Refresh */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">
            Executive Incident Telemetry
          </h2>
          <p className="text-xs text-dark-muted">
            30-day rolling window &middot; Live health status across microservices
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium bg-dark-surface border border-dark-border hover:border-slate-600 rounded-lg text-slate-300 hover:text-white transition-all shadow-sm"
        >
          <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
          <span>Refresh Telemetry</span>
        </button>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* KPI Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricCard
          title="Total Incidents"
          value={analytics?.total_incidents || 0}
          icon={<Layers size={18} />}
          subtitle="All recorded events"
        />
        <MetricCard
          title="Open"
          value={analytics?.open_incidents || 0}
          icon={<AlertOctagon size={18} className="text-rose-400" />}
          subtitle="Requiring triage"
        />
        <MetricCard
          title="Acknowledged"
          value={analytics?.acknowledged_incidents || 0}
          icon={<Clock size={18} className="text-amber-400" />}
          subtitle="Under active triage"
        />
        <MetricCard
          title="Resolved"
          value={analytics?.resolved_incidents || 0}
          icon={<CheckCircle2 size={18} className="text-emerald-400" />}
          subtitle="Mitigated & verified"
        />
        <MetricCard
          title="Critical"
          value={analytics?.critical_incidents || 0}
          icon={<AlertTriangle size={18} className="text-rose-400" />}
          subtitle="Priority 1 outages"
        />
        <MetricCard
          title="Resolution Rate"
          value={`${analytics?.resolution_rate_pct || 0}%`}
          icon={<TrendingUp size={18} className="text-indigo-400" />}
          subtitle="30-day velocity"
          trendPositive={Number(analytics?.resolution_rate_pct || 0) > 80}
        />
      </div>

      {/* Visual Analytics Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Trend Area Chart */}
        <div className="bg-dark-surface border border-dark-border rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Incident Ingestion Volume (Daily)
            </h3>
            <span className="text-[11px] text-dark-muted">Last 30 Days</span>
          </div>
          <div className="h-64 w-full">
            {analytics?.daily_trends && analytics.daily_trends.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={analytics.daily_trends}>
                  <defs>
                    <linearGradient id="incidentGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366F1" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#6366F1" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                  <XAxis
                    dataKey="date"
                    stroke="#8B949E"
                    fontSize={10}
                    tickFormatter={(val) => val.slice(5)}
                  />
                  <YAxis stroke="#8B949E" fontSize={10} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161B22',
                      borderColor: '#30363D',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="#6366F1"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#incidentGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-dark-muted">
                No historical trend points recorded in window.
              </div>
            )}
          </div>
        </div>

        {/* Severity Breakdown Bar Chart */}
        <div className="bg-dark-surface border border-dark-border rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Severity Distribution
            </h3>
            <span className="text-[11px] text-dark-muted">By Criticality</span>
          </div>
          <div className="h-64 w-full">
            {severityData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={severityData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                  <XAxis dataKey="severity" stroke="#8B949E" fontSize={11} />
                  <YAxis stroke="#8B949E" fontSize={10} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161B22',
                      borderColor: '#30363D',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="count" fill="#4F46E5" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-dark-muted">
                No severity counts available.
              </div>
            )}
          </div>
        </div>

        {/* Incidents by Microservice */}
        <div className="bg-dark-surface border border-dark-border rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Incidents by Microservice
            </h3>
            <span className="text-[11px] text-dark-muted">Impacted Services</span>
          </div>
          <div className="h-64 w-full">
            {serviceData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={serviceData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                  <XAxis type="number" stroke="#8B949E" fontSize={10} allowDecimals={false} />
                  <YAxis type="category" dataKey="service" stroke="#8B949E" fontSize={11} width={110} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161B22',
                      borderColor: '#30363D',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="count" fill="#0EA5E9" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-dark-muted">
                No service data logged yet.
              </div>
            )}
          </div>
        </div>

        {/* Status Distribution */}
        <div className="bg-dark-surface border border-dark-border rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Lifecycle Status Distribution
            </h3>
            <span className="text-[11px] text-dark-muted">Triage State</span>
          </div>
          <div className="h-64 w-full">
            {statusData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={statusData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                  <XAxis dataKey="status" stroke="#8B949E" fontSize={11} />
                  <YAxis stroke="#8B949E" fontSize={10} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161B22',
                      borderColor: '#30363D',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="count" fill="#10B981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-dark-muted">
                No status data available.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Incidents Quick Table */}
      <div className="bg-dark-surface border border-dark-border rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Recent Operational Incidents
            </h3>
            <p className="text-xs text-dark-muted">Most recent clustered anomalies</p>
          </div>
          <button
            onClick={() => navigate('/incidents')}
            className="flex items-center space-x-1 text-xs font-semibold text-indigo-400 hover:text-indigo-300"
          >
            <span>View All Incidents</span>
            <ArrowRight size={14} />
          </button>
        </div>

        {recentIncidents.length === 0 ? (
          <p className="text-xs text-dark-muted italic py-6 text-center">
            No active operational incidents recorded. System nominal.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-dark-bg/60 text-dark-muted border-b border-dark-border text-[11px] uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-3">ID & Title</th>
                  <th className="py-3 px-3">Service</th>
                  <th className="py-3 px-3">Severity</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Events</th>
                  <th className="py-3 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-border/40">
                {recentIncidents.map((inc) => (
                  <tr key={inc.incident_id} className="hover:bg-dark-hover/50 transition-colors">
                    <td className="py-3 px-3">
                      <div className="font-mono text-indigo-400 font-semibold">
                        {inc.incident_id}
                      </div>
                      <div className="text-slate-200 font-medium truncate max-w-sm">
                        {inc.title}
                      </div>
                    </td>
                    <td className="py-3 px-3 text-slate-300 font-mono text-[11px]">
                      {inc.service_name} ({inc.environment})
                    </td>
                    <td className="py-3 px-3">
                      <SeverityBadge severity={inc.severity} />
                    </td>
                    <td className="py-3 px-3">
                      <StatusBadge status={inc.status} />
                    </td>
                    <td className="py-3 px-3 text-slate-300 font-medium">
                      {inc.event_count}
                    </td>
                    <td className="py-3 px-3 text-right">
                      <button
                        onClick={() => navigate(`/incidents/${inc.incident_id}`)}
                        className="px-2.5 py-1 bg-dark-hover hover:bg-slate-700 text-slate-200 hover:text-white rounded border border-dark-border text-xs font-medium transition-colors"
                      >
                        Investigate &rarr;
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
