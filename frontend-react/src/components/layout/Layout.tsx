import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Navbar } from './Navbar';

const routeTitles: Record<string, { title: string; subtitle?: string }> = {
  '/': { title: 'Incident Response Overview', subtitle: 'Live operational telemetry and incident resolution health metrics.' },
  '/incidents': { title: 'Operational Incidents', subtitle: 'Active and resolved failure groups clustered by deterministic error signature.' },
  '/analysis': { title: 'AI Root-Cause Analysis', subtitle: 'Deep-reasoning incident diagnostics powered by Google Gemini 3.5 Flash Lite.' },
  '/precedents': { title: 'Historical Precedent Retrieval', subtitle: 'Atlas vector search similarity matches across resolved infrastructure failures.' },
  '/knowledge': { title: 'Operational Knowledge Base', subtitle: 'Verified incident resolutions repository empowering RAG investigations.' },
  '/analytics': { title: 'DevOps Incident Analytics', subtitle: 'Resolution velocity (MTTA/MTTR), failure distribution, and recurring signatures.' },
  '/logs': { title: 'Log Stream & Batch Ingestion', subtitle: 'Real-time telemetry ingestion, structured normalization, and signature clustering.' },
};

export const Layout: React.FC = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  // Find matching title for current pathname
  const currentPath = location.pathname;
  let pageInfo = routeTitles[currentPath];
  if (!pageInfo) {
    if (currentPath.startsWith('/incidents/')) {
      pageInfo = { title: 'Incident Details & Investigation', subtitle: 'Lifecycle management, audit trail, and verified resolution.' };
    } else if (currentPath.startsWith('/analysis/')) {
      pageInfo = { title: 'AI Root-Cause Diagnostic Run', subtitle: 'Grounded LLM hypothesis and remediation actions.' };
    } else {
      pageInfo = { title: 'OpsSage AI Command Center' };
    }
  }

  return (
    <div className="flex min-h-screen bg-dark-bg text-dark-text">
      <Sidebar mobileOpen={mobileOpen} onCloseMobile={() => setMobileOpen(false)} />
      
      <div className="flex-1 flex flex-col min-w-0">
        <Navbar
          onOpenMobile={() => setMobileOpen(true)}
          title={pageInfo.title}
          subtitle={pageInfo.subtitle}
        />
        
        <main className="flex-1 p-6 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
