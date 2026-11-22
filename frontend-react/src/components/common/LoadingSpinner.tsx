import React from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  fullPage?: boolean;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  label = 'Loading...',
  size = 'md',
  fullPage = false,
}) => {
  const iconSize = size === 'sm' ? 18 : size === 'lg' ? 36 : 24;

  const content = (
    <div className="flex flex-col items-center justify-center space-y-3 py-8">
      <Loader2 size={iconSize} className="animate-spin text-indigo-400" />
      {label && <p className="text-sm text-dark-muted font-medium">{label}</p>}
    </div>
  );

  if (fullPage) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-dark-bg">
        {content}
      </div>
    );
  }

  return content;
};
