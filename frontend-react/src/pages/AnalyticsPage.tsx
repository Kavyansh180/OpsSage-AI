import React, { useEffect, useState } from 'react';
import {
  BarChart3,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Repeat,
  Layers,
  RefreshCw,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { analyticsService } from '../services/analyticsService';
import { AnalyticsOverview } from '../types/analytics';
import { MetricCard } from '../components/common/MetricCard';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorBanner } from '../components/common/ErrorBanner';

export const AnalyticsPage: React.FC = () => {
  const [days, setDays] = useState(30);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalytics = async () => {
    setError(null);
    try {
      const data = await analyticsService.getOverview(days);
      setAnalytics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to query DevOps analytics.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, [days]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchAnalytics();
  };

  if (loading) {
    return <LoadingSpinner label="Computing DevOps incident velocity & recurrence..." />;
  }

  const envData = Object.entries(analytics?.by_environment || {}).map(([key, val]) => ({
    environment: key,
    count: val,
  }));

  const sevData = Object.entries(analytics?.by_severity || {}).map(([key, val]) => ({
    severity: key,
    count: val,
  }));

  const mttaDisplay =
    analytics?.mtta_minutes !== null && analytics?.mtta_minutes !== undefined
      ? `${analytics.mtta_minutes.toFixed(1)} min`
      : 'N/A';

  const mttrDisplay =
    analytics?.mttr_minutes !== null && analytics?.mttr_minutes !== undefined
      ? `${analytics.mttr_minutes.toFixed(1)} min`
      : 'N/A';

  return (
    <div className="space-y-6">
      {/* Top Banner and Window Selector */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center space-x-2">
            <BarChart3 size={20} className="text-indigo-400" />
            <span>DevOps Incident Analytics & Velocity</span>
          </h2>
          <p className="text-xs text-dark-muted">
            Triage speed metrics (MTTA/MTTR), failure signature recurrence, and environment distributions
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1.5 bg-dark-surface p-1 rounded-lg border border-dark-border text-xs font-semibold">
            {[7, 14, 30, 60, 90].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-2.5 py-1 rounded transition-all ${
                  days === d
                    ? 'bg-indigo-600 text-white shadow'
                    : 'text-dark-muted hover:text-white'
                }`}
              >
                {d}d
              </button>
            ))}
          </div>

          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="p-2 bg-dark-surface border border-dark-border hover:border-slate-600 rounded-lg text-slate-300 hover:text-white transition-all shadow-sm"
            aria-label="Refresh metrics"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* SRE Velocity KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Mean Time to Acknowledge (MTTA)"
          value={mttaDisplay}
          icon={<Clock size={18} className="text-amber-400" />}
          subtitle="Triage response latency"
        />
        <MetricCard
          title="Mean Time to Resolve (MTTR)"
          value={mttrDisplay}
          icon={<CheckCircle2 size={18} className="text-emerald-400" />}
          subtitle="Full mitigation velocity"
        />
        <MetricCard
          title="Resolution Rate"
          value={`${analytics?.resolution_rate_pct || 0}%`}
          icon={<Layers size={18} className="text-indigo-400" />}
          subtitle="Incidents marked resolved"
          trendPositive={Number(analytics?.resolution_rate_pct || 0) > 80}
        />
        <MetricCard
          title="Total Ingested"
          value={analytics?.total_incidents || 0}
          icon={<AlertTriangle size={18} className="text-rose-400" />}
          subtitle={`Window: ${days} days`}
        />
      </div>

      {/* Top Recurring Failure Patterns */}
      <div className="bg-dark-surface border border-dark-border rounded-xl p-5 space-y-4">
        <div className="flex items-center space-x-2">
          <Repeat size={18} className="text-indigo-400" />
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Top Recurring Failure Signatures
          </h3>
        </div>

        {analytics?.recurring_patterns && analytics.recurring_patterns.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-dark-bg/60 text-dark-muted border-b border-dark-border text-[11px] uppercase tracking-wider">
                <tr>
                  <th className="py-2.5 px-3">Recurrence</th>
                  <th className="py-2.5 px-3">Service</th>
                  <th className="py-2.5 px-3">Incident Title</th>
                  <th className="py-2.5 px-3">Severity</th>
                  <th className="py-2.5 px-3">Error Signature</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-border/40">
                {analytics.recurring_patterns.map((pat, idx) => (
                  <tr key={idx} className="hover:bg-dark-hover/50 transition-colors">
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span className="font-bold text-white bg-indigo-950/60 text-indigo-300 border border-indigo-800/40 px-2 py-0.5 rounded">
                        {pat.count}x events
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-slate-200">
                      {pat.service_name}
                    </td>
                    <td className="py-2.5 px-3 text-slate-300 font-medium max-w-sm truncate">
                      {pat.title}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {pat.severity}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-dark-muted max-w-xs truncate">
                      {pat.error_signature}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-dark-muted italic py-4 text-center">
            No recurring error signatures detected within the {days}-day analytics window.
          </p>
        )}
      </div>

      {/* Environment and Severity Breakdown Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-dark-surface border border-dark-border rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Incidents by Environment
          </h3>
          <div className="h-64 w-full">
            {envData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={envData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                  <XAxis dataKey="environment" stroke="#8B949E" fontSize={11} />
                  <YAxis stroke="#8B949E" fontSize={10} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161B22',
                      borderColor: '#30363D',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="count" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-dark-muted">
                No environment telemetry logged.
              </div>
            )}
          </div>
        </div>

        <div className="bg-dark-surface border border-dark-border rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Incidents by Severity
          </h3>
          <div className="h-64 w-full">
            {sevData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sevData}>
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
                  <Bar dataKey="count" fill="#EC4899" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-dark-muted">
                No severity data available.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
