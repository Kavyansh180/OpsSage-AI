import React from 'react';
import { CheckCircle2, ShieldCheck, ListChecks, Calendar, User } from 'lucide-react';
import { Incident } from '../../types/incident';

interface ResolutionCardProps {
  incident: Incident;
}

export const ResolutionCard: React.FC<ResolutionCardProps> = ({ incident }) => {
  if (!incident.confirmed_resolution) return null;

  return (
    <div className="bg-emerald-950/20 border border-emerald-800/60 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-emerald-800/40 pb-3">
        <div className="flex items-center space-x-2.5">
          <CheckCircle2 size={20} className="text-emerald-400" />
          <h4 className="text-sm font-bold text-white uppercase tracking-wider">
            Verified Resolution Finding
          </h4>
        </div>
        {incident.has_verified_resolution && (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-900/60 text-emerald-300 border border-emerald-700/50">
            <ShieldCheck size={14} className="mr-1" />
            Confirmed & Vector Synced
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        <div>
          <span className="font-semibold text-emerald-300 block mb-1">Diagnosed Root Cause:</span>
          <p className="text-slate-200 bg-dark-bg/60 p-3 rounded-lg border border-dark-border">
            {incident.confirmed_root_cause || 'Not specified'}
          </p>
        </div>
        <div>
          <span className="font-semibold text-emerald-300 block mb-1">Applied Mitigation / Fix:</span>
          <p className="text-slate-200 bg-dark-bg/60 p-3 rounded-lg border border-dark-border">
            {incident.confirmed_resolution}
          </p>
        </div>
      </div>

      {incident.resolution_actions && incident.resolution_actions.length > 0 && (
        <div className="text-xs pt-1">
          <div className="flex items-center space-x-1.5 font-semibold text-emerald-300 mb-2">
            <ListChecks size={15} />
            <span>Remediation Action Items Executed:</span>
          </div>
          <ul className="space-y-1 pl-1">
            {incident.resolution_actions.map((action, i) => (
              <li key={i} className="flex items-start space-x-2 text-slate-300">
                <span className="text-emerald-400 font-bold">✓</span>
                <span>{action}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-4 text-[11px] text-dark-muted border-t border-emerald-800/30 pt-3">
        {incident.verified_by && (
          <span className="flex items-center space-x-1">
            <User size={13} className="text-emerald-400" />
            <span>Verified by: <strong className="text-slate-200">{incident.verified_by}</strong></span>
          </span>
        )}
        {incident.resolved_at && (
          <span className="flex items-center space-x-1">
            <Calendar size={13} className="text-emerald-400" />
            <span>Resolved at: {new Date(incident.resolved_at).toLocaleString()}</span>
          </span>
        )}
      </div>
    </div>
  );
};
