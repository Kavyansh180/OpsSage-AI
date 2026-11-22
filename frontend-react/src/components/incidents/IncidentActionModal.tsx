import React, { useState } from 'react';
import { X, CheckCircle2, UserCheck, ShieldAlert } from 'lucide-react';
import { Incident, IncidentSeverity } from '../../types/incident';
import { incidentService } from '../../services/incidentService';
import { ErrorBanner } from '../common/ErrorBanner';

type ModalType = 'acknowledge' | 'assign' | 'severity' | 'resolve' | null;

interface IncidentActionModalProps {
  type: ModalType;
  incident: Incident;
  onClose: () => void;
  onSuccess: (updated: Incident) => void;
  currentUserEmail?: string;
}

export const IncidentActionModal: React.FC<IncidentActionModalProps> = ({
  type,
  incident,
  onClose,
  onSuccess,
  currentUserEmail = '',
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form states
  const [assignedTo, setAssignedTo] = useState(currentUserEmail);
  const [severity, setSeverity] = useState<IncidentSeverity>(incident.severity);
  const [rootCause, setRootCause] = useState(incident.confirmed_root_cause || '');
  const [resolution, setResolution] = useState(incident.confirmed_resolution || '');
  const [actionsRaw, setActionsRaw] = useState(
    (incident.resolution_actions || []).join('\n')
  );
  const [isVerified, setIsVerified] = useState(true);

  if (!type) return null;

  const handleAcknowledge = async () => {
    setLoading(true);
    setError(null);
    try {
      const updated = await incidentService.acknowledgeIncident(incident.incident_id);
      onSuccess(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to acknowledge incident.');
    } finally {
      setLoading(false);
    }
  };

  const handleAssign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignedTo.trim()) {
      setError('Please provide an engineer email or ID.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const updated = await incidentService.assignIncident(incident.incident_id, {
        assigned_to: assignedTo.trim(),
      });
      onSuccess(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to assign incident.');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateSeverity = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const updated = await incidentService.updateSeverity(incident.incident_id, {
        severity,
      });
      onSuccess(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update severity.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecordResolution = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rootCause.trim() || !resolution.trim()) {
      setError('Please provide both confirmed root cause and resolution description.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const actions = actionsRaw
        .split('\n')
        .map((a) => a.trim())
        .filter(Boolean);

      const updated = await incidentService.recordResolution(incident.incident_id, {
        confirmed_root_cause: rootCause.trim(),
        confirmed_resolution: resolution.trim(),
        resolution_actions: actions,
        is_verified: isVerified,
      });
      onSuccess(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to record resolution.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
      <div className="bg-dark-surface border border-dark-border rounded-xl shadow-2xl max-w-lg w-full overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-dark-border">
          <h3 className="text-base font-bold text-white flex items-center space-x-2">
            {type === 'acknowledge' && (
              <>
                <CheckCircle2 size={18} className="text-amber-400" />
                <span>Acknowledge Incident</span>
              </>
            )}
            {type === 'assign' && (
              <>
                <UserCheck size={18} className="text-indigo-400" />
                <span>Assign Incident</span>
              </>
            )}
            {type === 'severity' && (
              <>
                <ShieldAlert size={18} className="text-rose-400" />
                <span>Adjust Severity</span>
              </>
            )}
            {type === 'resolve' && (
              <>
                <CheckCircle2 size={18} className="text-emerald-400" />
                <span>Confirm & Resolve Incident</span>
              </>
            )}
          </h3>
          <button
            onClick={onClose}
            className="text-dark-muted hover:text-white p-1 rounded-lg hover:bg-dark-hover"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 space-y-4">
          {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

          {type === 'acknowledge' && (
            <div className="space-y-3">
              <p className="text-sm text-slate-300">
                You are acknowledging incident{' '}
                <strong className="text-white">{incident.incident_id}</strong> (
                {incident.title}).
              </p>
              <p className="text-xs text-dark-muted">
                This transitions the incident from <code>OPEN</code> to{' '}
                <code>ACKNOWLEDGED</code> and timestamps the on-call response time
                (MTTA).
              </p>
              <div className="flex justify-end space-x-3 pt-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-semibold text-slate-300 hover:text-white bg-dark-hover rounded-lg border border-dark-border"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleAcknowledge}
                  disabled={loading}
                  className="px-4 py-2 text-xs font-semibold text-white bg-amber-600 hover:bg-amber-500 rounded-lg shadow disabled:opacity-50"
                >
                  {loading ? 'Acknowledging...' : 'Confirm Acknowledgement'}
                </button>
              </div>
            </div>
          )}

          {type === 'assign' && (
            <form onSubmit={handleAssign} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Assignee Work Email / ID
                </label>
                <input
                  type="text"
                  value={assignedTo}
                  onChange={(e) => setAssignedTo(e.target.value)}
                  placeholder="e.g. srestart@company.com"
                  className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>
              <div className="flex justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-semibold text-slate-300 hover:text-white bg-dark-hover rounded-lg border border-dark-border"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg shadow disabled:opacity-50"
                >
                  {loading ? 'Assigning...' : 'Save Assignment'}
                </button>
              </div>
            </form>
          )}

          {type === 'severity' && (
            <form onSubmit={handleUpdateSeverity} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Incident Severity Rating
                </label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value as IncidentSeverity)}
                  className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="CRITICAL">CRITICAL — Severe Outage / Data Risk</option>
                  <option value="HIGH">HIGH — Degraded Core Service Flow</option>
                  <option value="MEDIUM">MEDIUM — Non-fatal / Recoverable Fault</option>
                  <option value="LOW">LOW — Minor Telemetry Anomaly</option>
                </select>
              </div>
              <div className="flex justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-semibold text-slate-300 hover:text-white bg-dark-hover rounded-lg border border-dark-border"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg shadow disabled:opacity-50"
                >
                  {loading ? 'Updating...' : 'Update Severity'}
                </button>
              </div>
            </form>
          )}

          {type === 'resolve' && (
            <form onSubmit={handleRecordResolution} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Confirmed Root Cause <span className="text-rose-400">*</span>
                </label>
                <textarea
                  value={rootCause}
                  onChange={(e) => setRootCause(e.target.value)}
                  placeholder="Describe the diagnosed technical failure mechanism..."
                  rows={2}
                  className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Resolution Summary <span className="text-rose-400">*</span>
                </label>
                <textarea
                  value={resolution}
                  onChange={(e) => setResolution(e.target.value)}
                  placeholder="Describe how the issue was fixed or mitigated..."
                  rows={2}
                  className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Action Items Taken (one per line)
                </label>
                <textarea
                  value={actionsRaw}
                  onChange={(e) => setActionsRaw(e.target.value)}
                  placeholder="e.g. Scaled database pool to 200&#10;Deployed composite index on order_id"
                  rows={3}
                  className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center space-x-2 pt-1">
                <input
                  type="checkbox"
                  id="is_verified"
                  checked={isVerified}
                  onChange={(e) => setIsVerified(e.target.checked)}
                  className="w-4 h-4 rounded border-dark-border text-emerald-500 focus:ring-0 bg-dark-bg cursor-pointer"
                />
                <label htmlFor="is_verified" className="text-xs text-slate-300 cursor-pointer">
                  Verify as Confirmed Solution (indexes into RAG Knowledge Base)
                </label>
              </div>

              <div className="flex justify-end space-x-3 pt-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-semibold text-slate-300 hover:text-white bg-dark-hover rounded-lg border border-dark-border"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg shadow disabled:opacity-50"
                >
                  {loading ? 'Saving & Syncing...' : 'Save & Resolve Incident'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
