import React from 'react';
import { IncidentSeverity } from '../../types/incident';

interface SeverityBadgeProps {
  severity: IncidentSeverity | string;
  className?: string;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity, className = '' }) => {
  const sev = (severity || 'LOW').toUpperCase();

  let styles = 'bg-emerald-950/80 text-emerald-400 border-emerald-800/60';
  if (sev === 'CRITICAL') {
    styles = 'bg-rose-950/80 text-rose-400 border-rose-800/60';
  } else if (sev === 'HIGH') {
    styles = 'bg-amber-950/80 text-amber-400 border-amber-800/60';
  } else if (sev === 'MEDIUM') {
    styles = 'bg-blue-950/80 text-blue-400 border-blue-800/60';
  }

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide border uppercase ${styles} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current" />
      {sev}
    </span>
  );
};
