import React from 'react';
import { IncidentStatus } from '../../types/incident';

interface StatusBadgeProps {
  status: IncidentStatus | string;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const st = (status || 'OPEN').toUpperCase();

  let styles = 'bg-rose-950/60 text-rose-300 border-rose-800/40';
  if (st === 'ACKNOWLEDGED') {
    styles = 'bg-amber-950/60 text-amber-300 border-amber-800/40';
  } else if (st === 'RESOLVED') {
    styles = 'bg-emerald-950/60 text-emerald-300 border-emerald-800/40';
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border uppercase tracking-wider ${styles} ${className}`}
    >
      {st}
    </span>
  );
};
