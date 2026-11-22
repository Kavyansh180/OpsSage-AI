import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle2,
  UserCheck,
  ShieldAlert,
  Sparkles,
  Calendar,
  Layers,
  Activity,
  User,
  AlertCircle,
  FileCheck,
} from 'lucide-react';
import { incidentService } from '../services/incidentService';
import { analysisService } from '../services/analysisService';
import { Incident, AuditHistoryEntry } from '../types/incident';
import { Analysis } from '../types/analysis';
import { useAuth } from '../context/AuthContext';
import { SeverityBadge } from '../components/common/SeverityBadge';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { ResolutionCard } from '../components/incidents/ResolutionCard';
import { InvestigationNotes } from '../components/incidents/InvestigationNotes';
import { AuditTimeline } from '../components/incidents/AuditTimeline';
import { IncidentActionModal } from '../components/incidents/IncidentActionModal';
import { TriggerRCAModal } from '../components/analysis/TriggerRCAModal';
import { RCARunCard } from '../components/analysis/RCARunCard';

export const IncidentDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user, isViewer } = useAuth();

  const [incident, setIncident] = useState<Incident | null>(null);
  const [history, setHistory] = useState<AuditHistoryEntry[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal controls
  const [actionModalType, setActionModalType] = useState<
    'acknowledge' | 'assign' | 'severity' | 'resolve' | null
  >(null);
  const [rcaModalOpen, setRcaModalOpen] = useState(false);

  const fetchIncidentData = async () => {
    if (!id) return;
    setError(null);
    try {
      const [incData, histData, anaData] = await Promise.all([
        incidentService.getIncident(id),
        incidentService.getIncidentHistory(id).catch(() => ({ items: [], total: 0 })),
        analysisService.getIncidentAnalyses(id).catch(() => ({ items: [], total: 0 })),
      ]);
      setIncident(incData);
      setHistory(histData.items || []);
      setAnalyses(anaData.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Incident '${id}' could not be loaded.`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidentData();
  }, [id]);

  if (loading) {
    return <LoadingSpinner label={`Loading incident ${id}...`} />;
  }

  if (!incident) {
    return (
      <div className="space-y-4">
        <ErrorBanner message={error || `Incident '${id}' not found.`} />
        <button
          onClick={() => navigate('/incidents')}
          className="flex items-center space-x-1.5 text-xs font-semibold text-indigo-400 hover:text-indigo-300"
        >
          <ArrowLeft size={14} />
          <span>Back to Incidents</span>
        </button>
      </div>
    );
  }

  const handleIncidentUpdated = (updated: Incident) => {
    setIncident(updated);
    // Refresh history
    if (id) {
      incidentService.getIncidentHistory(id).then((res) => setHistory(res.items || []));
    }
  };

  const handleRCASuccess = (newAnalysis: Analysis) => {
    setAnalyses((prev) => [newAnalysis, ...prev]);
  };

  return (
    <div className="space-y-6">
      {/* Back button and navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/incidents')}
          className="flex items-center space-x-1.5 text-xs font-semibold text-dark-muted hover:text-white transition-colors"
        >
          <ArrowLeft size={14} />
          <span>Back to Incidents</span>
        </button>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setRcaModalOpen(true)}
            disabled={isViewer}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-all shadow-md"
          >
            <Sparkles size={14} />
            <span>Trigger Gemini AI RCA</span>
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Incident Header Card */}
      <div className="bg-dark-surface border border-dark-border rounded-xl p-6 space-y-4 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2 flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityBadge severity={incident.severity} />
              <StatusBadge status={incident.status} />
              <span className="font-mono text-xs font-bold text-indigo-400 bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-800/40">
                {incident.incident_id}
              </span>
              {incident.has_verified_resolution && (
                <span className="inline-flex items-center text-[10px] font-semibold text-emerald-300 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/50">
                  <FileCheck size={12} className="mr-1 text-emerald-400" />
                  Verified Solution
                </span>
              )}
            </div>
            <h2 className="text-xl font-bold text-white tracking-tight">
              {incident.title}
            </h2>
          </div>

          {/* Quick Metrics */}
          <div className="flex flex-wrap gap-4 text-xs bg-dark-bg p-3 rounded-lg border border-dark-border shrink-0">
            <div>
              <span className="text-[10px] text-dark-muted uppercase font-semibold block">
                Assignee
              </span>
              <span className="font-medium text-slate-200">
                {incident.assigned_to || 'Unassigned'}
              </span>
            </div>
            <div className="border-l border-dark-border pl-4">
              <span className="text-[10px] text-dark-muted uppercase font-semibold block">
                Events Ingested
              </span>
              <span className="font-medium text-white">{incident.event_count}</span>
            </div>
          </div>
        </div>

        {/* Detailed Metadata Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs pt-2 border-t border-dark-border/60">
          <div>
            <span className="text-dark-muted block">Impacted Service</span>
            <span className="font-semibold text-slate-200">{incident.service_name}</span>
          </div>
          <div>
            <span className="text-dark-muted block">Environment</span>
            <span className="font-semibold text-slate-200">{incident.environment}</span>
          </div>
          <div>
            <span className="text-dark-muted block">First Observed</span>
            <span className="text-slate-300">
              {new Date(incident.first_seen).toLocaleString()}
            </span>
          </div>
          <div>
            <span className="text-dark-muted block">Last Incident Event</span>
            <span className="text-slate-300">
              {new Date(incident.last_seen).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Error Signature */}
        <div className="bg-dark-bg border border-dark-border rounded-lg p-3 text-xs font-mono text-slate-300 space-y-1">
          <div className="text-[10px] uppercase font-bold text-dark-muted tracking-wider">
            Deterministic Error Signature Hash
          </div>
          <div className="break-all text-indigo-300 font-mono text-[11px]">
            {incident.error_signature}
          </div>
        </div>

        {/* Engineer Lifecycle Actions */}
        <div className="pt-2">
          <div className="text-xs font-bold text-dark-muted uppercase tracking-wider mb-2">
            Incident Response Actions
          </div>
          <div className="flex flex-wrap gap-2.5">
            {/* Acknowledge */}
            <button
              onClick={() => setActionModalType('acknowledge')}
              disabled={isViewer || incident.status !== 'OPEN'}
              className="flex items-center space-x-1.5 px-3 py-2 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/40 rounded-lg text-xs font-semibold disabled:opacity-40 transition-all shadow-sm"
            >
              <CheckCircle2 size={14} />
              <span>Acknowledge Incident</span>
            </button>

            {/* Assign */}
            <button
              onClick={() => setActionModalType('assign')}
              disabled={isViewer}
              className="flex items-center space-x-1.5 px-3 py-2 bg-dark-hover hover:bg-slate-700 text-slate-200 border border-dark-border rounded-lg text-xs font-semibold disabled:opacity-40 transition-all shadow-sm"
            >
              <UserCheck size={14} />
              <span>Assign Engineer</span>
            </button>

            {/* Severity */}
            <button
              onClick={() => setActionModalType('severity')}
              disabled={isViewer}
              className="flex items-center space-x-1.5 px-3 py-2 bg-dark-hover hover:bg-slate-700 text-slate-200 border border-dark-border rounded-lg text-xs font-semibold disabled:opacity-40 transition-all shadow-sm"
            >
              <ShieldAlert size={14} />
              <span>Adjust Severity</span>
            </button>

            {/* Resolve */}
            <button
              onClick={() => setActionModalType('resolve')}
              disabled={isViewer}
              className="flex items-center space-x-1.5 px-3 py-2 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 rounded-lg text-xs font-semibold disabled:opacity-40 transition-all shadow-sm"
            >
              <CheckCircle2 size={14} />
              <span>Record Resolution</span>
            </button>
          </div>
        </div>
      </div>

      {/* Verified Resolution Display */}
      {incident.confirmed_resolution && <ResolutionCard incident={incident} />}

      {/* AI Root-Cause Analyses Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Sparkles size={18} className="text-indigo-400" />
            <h3 className="text-base font-bold text-white tracking-tight">
              AI Root-Cause Analyses ({analyses.length})
            </h3>
          </div>
          <button
            onClick={() => setRcaModalOpen(true)}
            disabled={isViewer}
            className="text-xs font-semibold text-indigo-400 hover:text-indigo-300"
          >
            + Run New Diagnostic
          </button>
        </div>

        {analyses.length === 0 ? (
          <div className="bg-dark-surface border border-dark-border rounded-xl p-6 text-center text-xs text-dark-muted space-y-2">
            <p>No AI root-cause diagnostics executed yet for this incident.</p>
            <button
              onClick={() => setRcaModalOpen(true)}
              disabled={isViewer}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-semibold shadow"
            >
              <Sparkles size={13} />
              <span>Execute Diagnostic Now</span>
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {analyses.map((ana, idx) => (
              <RCARunCard key={ana.analysis_id} analysis={ana} index={idx} />
            ))}
          </div>
        )}
      </div>

      {/* Investigation Notes & Audit History */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <InvestigationNotes
          incidentId={incident.incident_id}
          notes={incident.investigation_notes || []}
          onNoteAdded={(newNote) => {
            setIncident((prev) =>
              prev
                ? {
                    ...prev,
                    investigation_notes: [...(prev.investigation_notes || []), newNote],
                  }
                : null
            );
          }}
        />

        <AuditTimeline entries={history} />
      </div>

      {/* Action Modals */}
      <IncidentActionModal
        type={actionModalType}
        incident={incident}
        currentUserEmail={user?.email || ''}
        onClose={() => setActionModalType(null)}
        onSuccess={handleIncidentUpdated}
      />

      <TriggerRCAModal
        incidentId={incident.incident_id}
        isOpen={rcaModalOpen}
        onClose={() => setRcaModalOpen(false)}
        onSuccess={handleRCASuccess}
      />
    </div>
  );
};
