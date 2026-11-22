import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  AlertOctagon,
  Sparkles,
  BookOpen,
  Database,
  BarChart3,
  ScrollText,
  Shield,
  LogOut,
  X,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface SidebarProps {
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/incidents', label: 'Incidents', icon: AlertOctagon },
  { to: '/analysis', label: 'AI Root-Cause (RCA)', icon: Sparkles },
  { to: '/precedents', label: 'Precedent Retrieval', icon: BookOpen },
  { to: '/knowledge', label: 'Knowledge Base', icon: Database },
  { to: '/analytics', label: 'DevOps Analytics', icon: BarChart3 },
  { to: '/logs', label: 'Log Stream & Ingest', icon: ScrollText },
];

export const Sidebar: React.FC<SidebarProps> = ({ mobileOpen, onCloseMobile }) => {
  const { user, role, logout } = useAuth();

  const roleBadgeColor =
    role === 'admin'
      ? 'bg-rose-950/80 text-rose-300 border-rose-800/60'
      : role === 'engineer'
      ? 'bg-indigo-950/80 text-indigo-300 border-indigo-800/60'
      : 'bg-amber-950/80 text-amber-300 border-amber-800/60';

  const content = (
    <div className="flex flex-col h-full bg-dark-surface border-r border-dark-border w-64 select-none">
      {/* Brand Header */}
      <div className="flex items-center justify-between px-6 py-5 border-b border-dark-border">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-md shadow-indigo-600/30">
            <Shield size={20} />
          </div>
          <div>
            <div className="font-bold text-base tracking-tight text-white flex items-center space-x-1.5">
              <span>OpsSage AI</span>
            </div>
            <span className="text-[10px] text-dark-muted uppercase tracking-wider block font-medium">
              Autonomous SRE RCA
            </span>
          </div>
        </div>
        <button
          onClick={onCloseMobile}
          className="lg:hidden text-dark-muted hover:text-white transition-colors"
          aria-label="Close Sidebar"
        >
          <X size={20} />
        </button>
      </div>

      {/* User Information Pill */}
      <div className="px-5 py-4 border-b border-dark-border/60 bg-dark-bg/40">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-xs font-bold text-white">
            {user?.full_name?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-white truncate">{user?.full_name || 'Operator'}</p>
            <p className="text-[11px] text-dark-muted truncate">{user?.email}</p>
          </div>
        </div>
        <div className="mt-2.5 flex items-center justify-between">
          <span
            className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded border ${roleBadgeColor}`}
          >
            {role}
          </span>
          <span className="text-[10px] text-emerald-400 font-medium flex items-center">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1 animate-pulse" />
            Online
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-dark-muted">
          Platform Menu
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onCloseMobile}
              className={({ isActive }) =>
                `flex items-center space-x-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600/15 text-indigo-400 border border-indigo-500/30 font-semibold'
                    : 'text-dark-muted hover:text-white hover:bg-dark-hover/70'
                }`
              }
            >
              <Icon size={18} className="shrink-0" />
              <span className="truncate">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Sign Out Footer */}
      <div className="p-3 border-t border-dark-border">
        <button
          onClick={logout}
          className="w-full flex items-center justify-center space-x-2 px-3 py-2 rounded-lg text-xs font-medium text-rose-400 hover:bg-rose-950/30 hover:border-rose-800/40 border border-transparent transition-all"
        >
          <LogOut size={16} />
          <span>Sign Out</span>
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside className="hidden lg:flex shrink-0 h-screen sticky top-0">{content}</aside>

      {/* Mobile Drawer Overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
            onClick={onCloseMobile}
          />
          <div className="relative z-10 flex-1 flex max-w-xs w-full shadow-2xl">{content}</div>
        </div>
      )}
    </>
  );
};
