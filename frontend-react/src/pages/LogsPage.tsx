import React, { useEffect, useState } from 'react';
import {
  ScrollText,
  Filter,
  PlusCircle,
  RefreshCw,
  Clock,
  Layers,
  CheckCircle2,
  AlertCircle,
  X,
} from 'lucide-react';
import { logService } from '../services/logService';
import { LogEntry, BatchLogIngestResponse } from '../types/log';
import { useAuth } from '../context/AuthContext';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorBanner } from '../components/common/ErrorBanner';

export const LogsPage: React.FC = () => {
  const { isViewer } = useAuth();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [levelFilter, setLevelFilter] = useState('ALL');
  const [serviceFilter, setServiceFilter] = useState('ALL');
  const [envFilter, setEnvFilter] = useState('ALL');

  // Modal for Batch Ingestion
  const [modalOpen, setModalOpen] = useState(false);
  const [ingestServiceName, setIngestServiceName] = useState('checkout-service');
  const [ingestEnv, setIngestEnv] = useState('production');
  const [ingestMessage, setIngestMessage] = useState(
    'ConnectionResetError: Database connection pool exhausted on worker node during high checkout volume.'
  );
  const [batchCount, setBatchCount] = useState(5);
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<BatchLogIngestResponse | null>(null);

  const fetchLogs = async () => {
    setError(null);
    try {
      const data = await logService.listLogs({
        level: levelFilter,
        service_name: serviceFilter,
        environment: envFilter,
        limit: 100,
      });
      setLogs(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to query telemetry logs.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [levelFilter, serviceFilter, envFilter]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchLogs();
  };

  const handleBatchIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ingestMessage.trim()) return;

    setIngesting(true);
    setError(null);
    setIngestResult(null);

    try {
      const batchLogs = Array.from({ length: batchCount }, (_, idx) => ({
        service_name: ingestServiceName,
        environment: ingestEnv,
        level: 'ERROR',
        message: ingestMessage.trim(),
        source: 'api-worker',
        host: `worker-ap-south-1a-${idx + 1}`,
      }));

      const res = await logService.ingestBatchLogs({ logs: batchLogs });
      setIngestResult(res);
      fetchLogs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Log batch ingestion failed.');
    } finally {
      setIngesting(false);
    }
  };

  const getLevelBadge = (lvl: string) => {
    const l = (lvl || 'INFO').toUpperCase();
    if (l === 'CRITICAL' || l === 'ERROR') {
      return 'bg-rose-950/80 text-rose-300 border-rose-800/60';
    }
    if (l === 'WARN' || l === 'WARNING') {
      return 'bg-amber-950/80 text-amber-300 border-amber-800/60';
    }
    if (l === 'DEBUG') {
      return 'bg-slate-800 text-slate-400 border-slate-700';
    }
    return 'bg-blue-950/80 text-blue-300 border-blue-800/60';
  };

  return (
    <div className="space-y-6">
      {/* Top Banner and Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center space-x-2">
            <ScrollText size={20} className="text-indigo-400" />
            <span>Telemetry Log Stream & Batch Ingestion</span>
          </h2>
          <p className="text-xs text-dark-muted">
            Structured logs normalized by error signature clustering & sliding window anomaly detection
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setModalOpen(true)}
            disabled={isViewer}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-all shadow-md"
          >
            <PlusCircle size={14} />
            <span>Simulate / Ingest Logs</span>
          </button>

          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="p-2 bg-dark-surface border border-dark-border hover:border-slate-600 rounded-lg text-slate-300 hover:text-white transition-all shadow-sm"
            aria-label="Refresh logs"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Filter Bar */}
      <div className="bg-dark-surface border border-dark-border rounded-xl p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Level Filter */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-dark-muted mb-1 flex items-center space-x-1">
              <Filter size={11} />
              <span>Severity Level</span>
            </label>
            <select
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value)}
              className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Levels</option>
              <option value="ERROR">ERROR</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="WARN">WARN</option>
              <option value="INFO">INFO</option>
              <option value="DEBUG">DEBUG</option>
            </select>
          </div>

          {/* Service Filter */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-dark-muted mb-1 flex items-center space-x-1">
              <Layers size={11} />
              <span>Microservice</span>
            </label>
            <select
              value={serviceFilter}
              onChange={(e) => setServiceFilter(e.target.value)}
              className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Services</option>
              <option value="checkout-service">checkout-service</option>
              <option value="payment-gateway">payment-gateway</option>
              <option value="auth-service">auth-service</option>
              <option value="inventory-worker">inventory-worker</option>
            </select>
          </div>

          {/* Environment Filter */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-dark-muted mb-1 flex items-center space-x-1">
              <Clock size={11} />
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
        </div>
      </div>

      {/* Log Stream Table */}
      {loading ? (
        <LoadingSpinner label="Fetching telemetry log stream..." />
      ) : logs.length === 0 ? (
        <EmptyState
          title="No Logs Found"
          description="Click 'Simulate / Ingest Logs' above to ingest telemetry and observe real-time incident detection."
        />
      ) : (
        <div className="bg-dark-surface border border-dark-border rounded-xl overflow-hidden shadow-sm">
          <div className="px-5 py-3 border-b border-dark-border flex items-center justify-between text-xs text-dark-muted">
            <span>
              Stream View &middot; <strong className="text-white">{logs.length}</strong> record
              {logs.length === 1 ? '' : 's'}
            </span>
            <span className="text-[11px] text-emerald-400 font-medium">
              Live AWS Lambda Sink
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-dark-bg/60 text-dark-muted border-b border-dark-border text-[11px] uppercase tracking-wider">
                <tr>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Level</th>
                  <th className="py-2.5 px-3">Service</th>
                  <th className="py-2.5 px-3">Host / Source</th>
                  <th className="py-2.5 px-3">Message</th>
                  <th className="py-2.5 px-3">Signature</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-border/40 font-mono text-[11px]">
                {logs.map((log) => (
                  <tr key={log.log_id || log.id} className="hover:bg-dark-hover/50 transition-colors">
                    <td className="py-2.5 px-3 text-dark-muted whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wider border ${getLevelBadge(
                          log.level
                        )}`}
                      >
                        {log.level}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-indigo-300 font-medium whitespace-nowrap">
                      {log.service_name}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                      {log.host || log.source || '—'}
                    </td>
                    <td className="py-2.5 px-3 text-slate-200 font-sans text-xs max-w-md truncate">
                      {log.message}
                    </td>
                    <td className="py-2.5 px-3 text-dark-muted text-[10px] max-w-[120px] truncate">
                      {log.error_signature || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Batch Ingest Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
          <div className="bg-dark-surface border border-dark-border rounded-xl shadow-2xl max-w-lg w-full overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-dark-border">
              <h3 className="text-base font-bold text-white flex items-center space-x-2">
                <PlusCircle size={18} className="text-indigo-400" />
                <span>Simulate / Ingest Telemetry Batch</span>
              </h3>
              <button
                onClick={() => setModalOpen(false)}
                className="text-dark-muted hover:text-white p-1 rounded-lg hover:bg-dark-hover"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleBatchIngest} className="p-6 space-y-4">
              {ingestResult && (
                <div className="p-3 bg-emerald-950/40 border border-emerald-800/60 rounded-lg text-emerald-300 text-xs space-y-1">
                  <div className="flex items-center space-x-1.5 font-bold">
                    <CheckCircle2 size={15} className="text-emerald-400" />
                    <span>Batch Ingestion Successful!</span>
                  </div>
                  <p>
                    Ingested: {ingestResult.successful_count} logs &middot; Failed:{' '}
                    {ingestResult.failed_count}
                  </p>
                  {ingestResult.incident_triggered && (
                    <p className="font-bold text-amber-300 pt-1">
                      🚨 Threshold reached! Clustered into Incident:{' '}
                      <code className="text-white">{ingestResult.incident_id}</code>
                    </p>
                  )}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Microservice
                  </label>
                  <input
                    type="text"
                    value={ingestServiceName}
                    onChange={(e) => setIngestServiceName(e.target.value)}
                    className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Environment
                  </label>
                  <select
                    value={ingestEnv}
                    onChange={(e) => setIngestEnv(e.target.value)}
                    className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value="production">production</option>
                    <option value="staging">staging</option>
                    <option value="development">development</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Error Log Message Template
                </label>
                <textarea
                  value={ingestMessage}
                  onChange={(e) => setIngestMessage(e.target.value)}
                  rows={3}
                  className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Batch Count: <strong className="text-white">{batchCount} logs</strong>
                </label>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={batchCount}
                  onChange={(e) => setBatchCount(parseInt(e.target.value, 10))}
                  className="w-full h-1 bg-dark-border rounded-lg appearance-none cursor-pointer accent-indigo-500"
                />
                <p className="text-[10px] text-dark-muted mt-1">
                  Ingesting 3 or more uniform error logs within the sliding window triggers automatic incident clustering.
                </p>
              </div>

              <div className="flex justify-end space-x-3 pt-3 border-t border-dark-border">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-300 hover:text-white bg-dark-hover rounded-lg border border-dark-border"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={ingesting || !ingestMessage.trim()}
                  className="px-5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-lg shadow flex items-center space-x-1.5"
                >
                  <PlusCircle size={14} />
                  <span>{ingesting ? 'Ingesting...' : 'Ingest Batch'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
