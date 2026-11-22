import React from 'react';
import { Menu, Activity, ShieldCheck, ExternalLink } from 'lucide-react';
import { API_BASE_URL } from '../../services/api';

interface NavbarProps {
  onOpenMobile: () => void;
  title?: string;
  subtitle?: string;
}

export const Navbar: React.FC<NavbarProps> = ({
  onOpenMobile,
  title = 'Incident Response Overview',
  subtitle,
}) => {
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between h-16 px-6 bg-dark-surface/90 backdrop-blur border-b border-dark-border">
      <div className="flex items-center space-x-4">
        <button
          onClick={onOpenMobile}
          className="lg:hidden p-2 text-dark-muted hover:text-white rounded-lg hover:bg-dark-hover"
          aria-label="Open Navigation"
        >
          <Menu size={20} />
        </button>
        <div>
          <h1 className="text-base font-bold text-white tracking-tight flex items-center space-x-2">
            <span>{title}</span>
          </h1>
          {subtitle && <p className="text-xs text-dark-muted">{subtitle}</p>}
        </div>
      </div>

      <div className="flex items-center space-x-4">
        {/* Backend Connectivity Status Badge */}
        <div className="hidden sm:flex items-center space-x-2 px-3 py-1 bg-emerald-950/40 border border-emerald-800/40 rounded-full text-emerald-400 text-xs font-medium">
          <Activity size={14} className="animate-pulse" />
          <span>AWS Serverless ap-south-1</span>
        </div>

        {/* API Docs Link */}
        <a
          href={`${API_BASE_URL.replace('/api/v1', '')}/docs`}
          target="_blank"
          rel="noreferrer"
          className="hidden md:flex items-center space-x-1.5 px-3 py-1.5 text-xs text-dark-muted hover:text-white bg-dark-hover rounded-lg border border-dark-border hover:border-slate-600 transition-colors"
        >
          <ShieldCheck size={14} className="text-indigo-400" />
          <span>FastAPI Docs</span>
          <ExternalLink size={12} className="opacity-70" />
        </a>
      </div>
    </header>
  );
};
