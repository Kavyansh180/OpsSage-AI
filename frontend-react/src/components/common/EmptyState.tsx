import React from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  action,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center bg-dark-surface/50 border border-dashed border-dark-border rounded-xl">
      <div className="w-12 h-12 flex items-center justify-center rounded-full bg-slate-800 text-dark-muted mb-3">
        {icon || <Inbox size={24} />}
      </div>
      <h3 className="text-base font-semibold text-white mb-1">{title}</h3>
      {description && <p className="text-sm text-dark-muted max-w-sm mb-4">{description}</p>}
      {action && <div>{action}</div>}
    </div>
  );
};
