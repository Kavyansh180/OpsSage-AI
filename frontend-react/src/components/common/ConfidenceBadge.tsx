import React from 'react';
import { ConfidenceLevel } from '../../types/analysis';

interface ConfidenceBadgeProps {
  confidence: ConfidenceLevel | string;
  className?: string;
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ confidence, className = '' }) => {
  const conf = (confidence || 'LOW').toUpperCase();

  let styles = 'bg-purple-950/80 text-purple-300 border-purple-700/50';
  if (conf === 'HIGH') {
    styles = 'bg-emerald-950/80 text-emerald-300 border-emerald-700/50';
  } else if (conf === 'MEDIUM') {
    styles = 'bg-blue-950/80 text-blue-300 border-blue-700/50';
  }

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide border uppercase ${styles} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current" />
      {conf} CONFIDENCE
    </span>
  );
};
