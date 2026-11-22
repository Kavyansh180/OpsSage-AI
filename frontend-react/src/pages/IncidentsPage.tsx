import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Filter,
  AlertOctagon,
  Sparkles,
  ShieldCheck,
  Calendar,
  Layers,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import { incidentService } from '../services/incidentService';
import { Incident } from '../types/incident';
import { SeverityBadge } from '../components/common/SeverityBadge';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorBanner } from '../components/common/ErrorBanner';

export const IncidentsPage: React.FC = () => {
  const navigate = useNavigate();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [sevFilter, setSevFilter] = useState('ALL');
  const [envFilter, setEnvFilter] = useState('ALL');
  const [searchKeyword, setSearchKeyword] = useState('');

  const fetchIncidents = async () => {
    setError(null);
    try {
      const data = await incidentService.listIncidents({
        status: statusFilter,
        severity: sevFilter,
        environment: envFilter,
        limit: 100,
      });
      setIncidents(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to query incidents.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, [statusFilter, sevFilter, envFilter]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchIncidents();
  };

  // Client-side search keyword filtering for instantaneous UX
  const filtered = incidents.filter((inc) => {
    if (!searchKeyword.trim()) return true;
    const kw = searchKeyword.toLowerCase();
    return (
      inc.title.toLowerCase().includes(kw) ||
      inc.service_name.toLowerCase().includes(kw) ||
      inc.incident_id.toLowerCase().includes(kw) ||
      inc.error_signature.toLowerCase().includes(kw)
    );
  });

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">
            Operational Incidents Command Center
          </h2>
          <p className="text-xs text-dark-muted">
            Deterministic failure groups automatically clustered by error signature
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium bg-dark-surface border border-dark-border hover:border-slate-600 rounded-lg text-slate-300 hover:text-white transition-all shadow-sm"
        >
          <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Filter and Search Bar */}
      <div className="bg-dark-surface border border-dark-border rounded-xl p-4 space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Status Filter */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-dark-muted mb-1 flex items-center space-x-1">
              <Filter size={11} />
              <span>Status</span>
            </label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="OPEN">Open (Requires Triage)</option>
              <option value="ACKNOWLEDGED">Acknowledged (Under Investigation)</option>
              <option value="RESOLVED">Resolved (Verified)</option>
            </select>
          </div>

          {/* Severity Filter */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-dark-muted mb-1 flex items-center space-x-1">
              <AlertOctagon size={11} />
              <span>Severity</span>
            </label>
            <select
              value={sevFilter}
              onChange={(e) => setSevFilter(e.target.value)}
              className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>

          {/* Environment Filter */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-dark-muted mb-1 flex items-center space-x-1">
              <Layers size={11} />
              <span>Environment</span>
            </label>
            <select
              value={envFilter}
              onChange={(e) => setEnvFilter(e.target.value)}
              className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Environments</option>
              <option value="production">Production</option>
              <option value="staging">Staging</option>
              <option value="development">Development</option>
            </select>
          </div>

          {/* Search Box */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-dark-muted mb-1 flex items-center space-x-1">
              <Search size={11} />
              <span>Keyword Search</span>
            </label>
            <input
              type="text"
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              placeholder="e.g. pool, timeout, checkout..."
              className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 placeholder-dark-muted"
            />
          </div>
        </div>

        <div className="flex items-center justify-between text-[11px] text-dark-muted pt-1 border-t border-dark-border/40">
          <span>
            Showing <strong className="text-white">{filtered.length}</strong> incident
            {filtered.length === 1 ? '' : 's'} (Total in DB: {total})
          </span>
          {(statusFilter !== 'ALL' || sevFilter !== 'ALL' || envFilter !== 'ALL' || searchKeyword) && (
            <button
              onClick={() => {
                setStatusFilter('ALL');
                setSevFilter('ALL');
                setEnvFilter('ALL');
                setSearchKeyword('');
              }}
              className="text-indigo-400 hover:text-indigo-300 font-semibold"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Incident List */}
      {loading ? (
        <LoadingSpinner label="Querying incidents..." />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No Incidents Found"
          description="No operational incidents match your filter parameters or search query."
        />
      ) : (
        <div className="space-y-3">
          {filtered.map((inc) => (
            <div
              key={inc.incident_id}
              className="bg-dark-surface border border-dark-border rounded-xl p-5 hover:border-slate-600 transition-all shadow-sm space-y-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <SeverityBadge severity={inc.severity} />
                    <StatusBadge status={inc.status} />
                    <span className="font-mono text-xs font-bold text-indigo-400 bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-800/40">
                      {inc.incident_id}
                    </span>
                    {inc.has_verified_resolution && (
                      <span className="inline-flex items-center text-[10px] font-semibold text-emerald-300 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/50">
                        <ShieldCheck size={12} className="mr-1 text-emerald-400" />
                        Verified Resolution
                      </span>
                    )}
                  </div>
                  <h3 className="text-base font-bold text-white tracking-tight truncate">
                    {inc.title}
                  </h3>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-dark-muted">
                    <span>
                      Service: <strong className="text-slate-200">{inc.service_name}</strong>
                    </span>
                    <span>&middot;</span>
                    <span>
                      Environment: <strong className="text-slate-200">{inc.environment}</strong>
                    </span>
                    <span>&middot;</span>
                    <span>
                      Events Ingested: <strong className="text-slate-200">{inc.event_count}</strong>
                    </span>
                    <span>&middot;</span>
                    <span className="flex items-center space-x-1">
                      <Calendar size={12} />
                      <span>Last Seen: {new Date(inc.last_seen).toLocaleTimeString()}</span>
                    </span>
                  </div>
                </div>

                {/* Quick Actions */}
                <div className="flex items-center space-x-2 shrink-0">
                  <button
                    onClick={() => navigate(`/analysis/${inc.incident_id}`)}
                    className="flex items-center space-x-1 px-3 py-2 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 rounded-lg text-xs font-semibold transition-all shadow-sm"
                  >
                    <Sparkles size={13} className="text-indigo-400" />
                    <span>AI RCA</span>
                  </button>
                  <button
                    onClick={() => navigate(`/incidents/${inc.incident_id}`)}
                    className="flex items-center space-x-1.5 px-3 py-2 bg-dark-hover hover:bg-slate-700 text-white rounded-lg border border-dark-border text-xs font-semibold transition-all shadow-sm"
                  >
                    <span>Investigate</span>
                    <ArrowRight size={13} />
                  </button>
                </div>
              </div>

              {/* Error Signature Code Snippet */}
              <div className="bg-dark-bg border border-dark-border/60 rounded px-3 py-2 text-[11px] font-mono text-slate-400 truncate flex items-center space-x-2">
                <span className="text-dark-muted font-bold text-[10px] uppercase">
                  Signature:
                </span>
                <span className="truncate">{inc.error_signature}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
