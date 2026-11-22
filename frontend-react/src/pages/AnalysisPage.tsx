import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Sparkles, Search, AlertCircle, RefreshCw } from 'lucide-react';
import { analysisService } from '../services/analysisService';
import { incidentService } from '../services/incidentService';
import { Analysis } from '../types/analysis';
import { Incident } from '../types/incident';
import { useAuth } from '../context/AuthContext';
import { RCARunCard } from '../components/analysis/RCARunCard';
import { TriggerRCAModal } from '../components/analysis/TriggerRCAModal';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorBanner } from '../components/common/ErrorBanner';

export const AnalysisPage: React.FC = () => {
  const { id: routeIncidentId } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const { isViewer } = useAuth();

  const [selectedIncidentId, setSelectedIncidentId] = useState(routeIncidentId || '');
  const [incidentsList, setIncidentsList] = useState<Incident[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingList, setLoadingList] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rcaModalOpen, setRcaModalOpen] = useState(false);

  // Load available incidents for dropdown selector
  useEffect(() => {
    incidentService
      .listIncidents({ limit: 50 })
      .then((data) => {
        setIncidentsList(data.items || []);
        if (!selectedIncidentId && data.items && data.items.length > 0) {
          setSelectedIncidentId(data.items[0].incident_id);
        }
      })
      .catch(() => {})
      .finally(() => setLoadingList(false));
  }, []);

  // Update selected incident if route param changes
  useEffect(() => {
    if (routeIncidentId) {
      setSelectedIncidentId(routeIncidentId);
    }
  }, [routeIncidentId]);

  // Load analyses for selected incident
  const fetchAnalyses = async (incId: string) => {
    if (!incId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await analysisService.getIncidentAnalyses(incId.trim());
      setAnalyses(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to query analyses.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedIncidentId) {
      fetchAnalyses(selectedIncidentId);
    }
  }, [selectedIncidentId]);

  const handleSelectIncident = (id: string) => {
    setSelectedIncidentId(id);
    navigate(`/analysis/${id}`);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center space-x-2">
            <Sparkles size={20} className="text-indigo-400" />
            <span>AI Root-Cause Analysis Command Center</span>
          </h2>
          <p className="text-xs text-dark-muted">
            Deep-reasoning diagnostics grounded by telemetry and Google Gemini 3.5 Flash Lite
          </p>
        </div>

        {selectedIncidentId && (
          <button
            onClick={() => setRcaModalOpen(true)}
            disabled={isViewer}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-all shadow-md"
          >
            <Sparkles size={14} />
            <span>Run New RCA Diagnostic</span>
          </button>
        )}
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Incident Selector Bar */}
      <div className="bg-dark-surface border border-dark-border rounded-xl p-4">
        <label className="block text-[11px] font-semibold uppercase tracking-wider text-dark-muted mb-2 flex items-center space-x-1.5">
          <Search size={13} />
          <span>Select Target Incident</span>
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[240px]">
            <select
              value={selectedIncidentId}
              onChange={(e) => handleSelectIncident(e.target.value)}
              className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
              disabled={loadingList}
            >
              <option value="">-- Choose an Incident --</option>
              {incidentsList.map((inc) => (
                <option key={inc.incident_id} value={inc.incident_id}>
                  [{inc.severity}] {inc.incident_id} — {inc.title} ({inc.service_name})
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <input
              type="text"
              value={selectedIncidentId}
              onChange={(e) => setSelectedIncidentId(e.target.value)}
              placeholder="Or enter incident ID..."
              className="w-48 bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
            />
            <button
              onClick={() => fetchAnalyses(selectedIncidentId)}
              className="px-3 py-2 bg-dark-hover hover:bg-slate-700 text-white rounded-lg border border-dark-border text-xs font-medium"
            >
              Load
            </button>
          </div>
        </div>
      </div>

      {/* Analyses List */}
      {loading ? (
        <LoadingSpinner label={`Querying diagnostic history for ${selectedIncidentId}...`} />
      ) : !selectedIncidentId ? (
        <EmptyState
          title="Select an Incident to Inspect Diagnostics"
          description="Choose an incident from the dropdown above or enter an ID to view Gemini root-cause analyses."
        />
      ) : analyses.length === 0 ? (
        <EmptyState
          title={`No Analyses Found for ${selectedIncidentId}`}
          description="Click 'Run New RCA Diagnostic' above to analyze raw telemetry logs and historical precedents via Gemini."
          action={
            <button
              onClick={() => setRcaModalOpen(true)}
              disabled={isViewer}
              className="inline-flex items-center space-x-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow"
            >
              <Sparkles size={14} />
              <span>Run Diagnostic Now</span>
            </button>
          }
        />
      ) : (
        <div className="space-y-6">
          <div className="flex items-center justify-between text-xs text-dark-muted border-b border-dark-border/40 pb-2">
            <span>
              Target: <strong className="text-white font-mono">{selectedIncidentId}</strong> &middot;{' '}
              {analyses.length} Diagnostic Run{analyses.length === 1 ? '' : 's'}
            </span>
          </div>

          {analyses.map((ana, idx) => (
            <RCARunCard key={ana.analysis_id} analysis={ana} index={idx} />
          ))}
        </div>
      )}

      {/* Trigger RCA Modal */}
      {selectedIncidentId && (
        <TriggerRCAModal
          incidentId={selectedIncidentId}
          isOpen={rcaModalOpen}
          onClose={() => setRcaModalOpen(false)}
          onSuccess={(newAna) => setAnalyses((prev) => [newAna, ...prev])}
        />
      )}
    </div>
  );
};
