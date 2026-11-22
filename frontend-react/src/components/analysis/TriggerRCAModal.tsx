import React, { useState } from 'react';
import { X, Sparkles, AlertCircle } from 'lucide-react';
import { analysisService } from '../../services/analysisService';
import { Analysis } from '../../types/analysis';
import { ErrorBanner } from '../common/ErrorBanner';

interface TriggerRCAModalProps {
  incidentId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (analysis: Analysis) => void;
}

export const TriggerRCAModal: React.FC<TriggerRCAModalProps> = ({
  incidentId,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [context, setContext] = useState('');
  const [maxLogs, setMaxLogs] = useState(25);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await analysisService.triggerRCA(incidentId, {
        additional_context: context.trim() || undefined,
        max_evidence_logs: maxLogs,
      });
      onSuccess(result);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI Root-Cause Analysis failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
      <div className="bg-dark-surface border border-dark-border rounded-xl shadow-2xl max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-dark-border">
          <div className="flex items-center space-x-2">
            <Sparkles size={18} className="text-indigo-400" />
            <h3 className="text-base font-bold text-white">
              Execute AI Root-Cause Analysis
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-dark-muted hover:text-white p-1 rounded-lg hover:bg-dark-hover"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

          <div className="bg-indigo-950/20 border border-indigo-800/40 rounded-lg p-3 text-xs text-indigo-300 space-y-1">
            <div className="flex items-center space-x-1.5 font-bold">
              <AlertCircle size={14} />
              <span>Target Incident: {incidentId}</span>
            </div>
            <p className="text-[11px] text-indigo-200/80">
              This triggers the deep-reasoning Gemini 3.5 Flash Lite pipeline, retrieving
              normalized error signatures, sanitizing sensitive tokens, and querying Atlas
              Vector Search for matching historical resolutions.
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Operator Context / Human Notes (Optional)
            </label>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="e.g. Deployed microservice release v2.4.1 10 minutes prior, or observed database connection spikes during sale..."
              rows={3}
              className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 placeholder-dark-muted"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Max Telemetry Logs as Evidence ({maxLogs})
            </label>
            <input
              type="range"
              min="5"
              max="50"
              step="5"
              value={maxLogs}
              onChange={(e) => setMaxLogs(parseInt(e.target.value, 10))}
              className="w-full h-1 bg-dark-border rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />
            <div className="flex justify-between text-[10px] text-dark-muted mt-1">
              <span>5 logs</span>
              <span>25 logs (default)</span>
              <span>50 logs</span>
            </div>
          </div>

          <div className="flex justify-end space-x-3 pt-3 border-t border-dark-border">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-xs font-semibold text-slate-300 hover:text-white bg-dark-hover rounded-lg border border-dark-border"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-lg shadow flex items-center space-x-2"
            >
              <Sparkles size={14} className={loading ? 'animate-spin' : ''} />
              <span>{loading ? 'Reasoning with Gemini...' : 'Start RCA Pipeline'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
