import React, { useState, useEffect } from 'react';
import { Database, Search, ShieldCheck, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { knowledgeService } from '../services/knowledgeService';
import { KnowledgeDocument } from '../types/knowledge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorBanner } from '../components/common/ErrorBanner';

export const KnowledgeBasePage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null);

  const fetchKnowledge = async (searchTerm: string) => {
    setLoading(true);
    setError(null);
    setSearched(true);
    try {
      const data = await knowledgeService.searchKnowledge({
        query: searchTerm.trim() || 'operational error failure database network',
        top_k: 10,
        min_similarity: 0.3,
      });
      setDocuments(data.results || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Knowledge query failed.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKnowledge('system incident exception error');
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchKnowledge(query);
  };

  const toggleExpand = (id: string) => {
    setExpandedDocId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div>
        <h2 className="text-xl font-bold text-white tracking-tight flex items-center space-x-2">
          <Database size={20} className="text-indigo-400" />
          <span>Operational Knowledge Base</span>
        </h2>
        <p className="text-xs text-dark-muted">
          Persistent repository of verified incident resolutions empowering RAG investigations
        </p>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Search Input */}
      <form onSubmit={handleSearchSubmit} className="bg-dark-surface border border-dark-border rounded-xl p-4">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-muted" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search verified resolutions (e.g. database pool exhaustion, memory leak, expired cert)..."
            className="w-full bg-dark-bg border border-dark-border rounded-lg pl-9 pr-24 py-2.5 text-xs text-white focus:outline-none focus:border-indigo-500 placeholder-dark-muted"
          />
          <button
            type="submit"
            disabled={loading}
            className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-md text-xs font-semibold shadow"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </form>

      {/* Document List */}
      {loading ? (
        <LoadingSpinner label="Querying vector knowledge records..." />
      ) : searched && documents.length === 0 ? (
        <EmptyState
          title="No Knowledge Base Documents Found"
          description="Resolve operational incidents and mark them as verified solutions to automatically index them here."
        />
      ) : (
        <div className="space-y-3">
          <div className="text-xs text-dark-muted">
            Displaying <strong className="text-white">{documents.length}</strong> indexed knowledge record{documents.length === 1 ? '' : 's'}:
          </div>

          {documents.map((doc) => {
            const isExpanded = expandedDocId === (doc.knowledge_id || doc.id);
            return (
              <div
                key={doc.knowledge_id || doc.id}
                className="bg-dark-surface border border-dark-border rounded-xl overflow-hidden transition-all shadow-sm"
              >
                <div
                  onClick={() => toggleExpand(doc.knowledge_id || doc.id)}
                  className="p-5 flex items-start justify-between cursor-pointer hover:bg-dark-hover/40 transition-colors select-none"
                >
                  <div className="space-y-1.5 flex-1 min-w-0 pr-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-bold text-indigo-400 bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-800/40">
                        {doc.knowledge_id || 'KB-DOC'}
                      </span>
                      <span className="font-mono text-xs text-dark-muted">
                        Source: {doc.source_incident_id}
                      </span>
                      {doc.has_verified_resolution && (
                        <span className="inline-flex items-center text-[10px] font-semibold text-emerald-300 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/50">
                          <ShieldCheck size={12} className="mr-1 text-emerald-400" />
                          Verified
                        </span>
                      )}
                    </div>
                    <h3 className="text-sm font-bold text-white tracking-tight">{doc.title}</h3>
                    <div className="text-xs text-dark-muted">
                      Service: <strong className="text-slate-200">{doc.service_name}</strong> &middot;{' '}
                      Environment: <strong className="text-slate-200">{doc.environment}</strong>
                    </div>
                  </div>

                  <div className="text-dark-muted p-1">
                    {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                  </div>
                </div>

                {/* Collapsible Details */}
                {isExpanded && (
                  <div className="px-5 pb-5 pt-1 space-y-4 border-t border-dark-border/40 text-xs">
                    {doc.diagnostic_summary && (
                      <div>
                        <span className="font-bold text-dark-muted uppercase text-[10px] block mb-1">
                          Diagnostic Summary
                        </span>
                        <p className="text-slate-200 bg-dark-bg p-3 rounded-lg border border-dark-border leading-relaxed">
                          {doc.diagnostic_summary}
                        </p>
                      </div>
                    )}

                    {doc.confirmed_resolution && (
                      <div className="p-3 bg-emerald-950/30 border border-emerald-800/40 rounded-lg text-emerald-200 space-y-1">
                        <span className="font-bold uppercase tracking-wider text-emerald-400 text-[10px] block">
                          Verified Resolution Summary
                        </span>
                        <p>{doc.confirmed_resolution}</p>
                      </div>
                    )}

                    {doc.historical_analysis?.probable_root_cause && (
                      <div className="p-3 bg-purple-950/30 border border-purple-800/40 rounded-lg text-purple-200 space-y-1">
                        <span className="font-bold uppercase tracking-wider text-purple-400 text-[10px] block">
                          Historical AI Root-Cause Hypothesis
                        </span>
                        <p>{doc.historical_analysis.probable_root_cause}</p>
                      </div>
                    )}

                    <div className="text-[11px] text-dark-muted flex justify-between pt-1">
                      <span>Error Signature: <code className="text-slate-400">{doc.error_signature}</code></span>
                      <span>Created: {new Date(doc.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
