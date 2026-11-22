import React from 'react';
import { History, Clock, User } from 'lucide-react';
import { AuditHistoryEntry } from '../../types/incident';

interface AuditTimelineProps {
  entries: AuditHistoryEntry[];
}

const formatDetails = (details: unknown): string => {
  if (!details) return '—';
  if (typeof details === 'object') {
    try {
      return JSON.stringify(details);
    } catch {
      return String(details);
    }
  }
  return String(details);
};

export const AuditTimeline: React.FC<AuditTimelineProps> = ({ entries }) => {
  return (
    <div className="bg-dark-surface border border-dark-border rounded-xl p-5 space-y-4">
      <div className="flex items-center space-x-2 border-b border-dark-border pb-3">
        <History size={18} className="text-amber-400" />
        <h4 className="text-sm font-bold text-white uppercase tracking-wider">
          Immutable Audit Trail ({entries.length})
        </h4>
      </div>

      {entries.length === 0 ? (
        <p className="text-xs text-dark-muted italic py-3 text-center">
          No audit history events recorded for this incident.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-dark-bg/60 text-dark-muted border-b border-dark-border text-[11px] uppercase tracking-wider">
              <tr>
                <th className="py-2.5 px-3">Timestamp</th>
                <th className="py-2.5 px-3">Action</th>
                <th className="py-2.5 px-3">Actor</th>
                <th className="py-2.5 px-3">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-border/40">
              {entries.map((entry, idx) => (
                <tr key={idx} className="hover:bg-dark-hover/50 transition-colors">
                  <td className="py-2.5 px-3 whitespace-nowrap text-dark-muted flex items-center space-x-1.5">
                    <Clock size={12} className="text-indigo-400 shrink-0" />
                    <span>{new Date(entry.timestamp).toLocaleString()}</span>
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
                      {entry.action}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap text-slate-300">
                    <span className="flex items-center space-x-1">
                      <User size={12} className="text-dark-muted" />
                      <span>{entry.actor_email}</span>
                    </span>
                  </td>
                  <td 
                    className="py-2.5 px-3 text-slate-400 font-mono text-[11px] max-w-xs truncate"
                    title={typeof entry.details === 'object' ? JSON.stringify(entry.details, null, 2) : String(entry.details || '')}
                  >
                    {formatDetails(entry.details)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
