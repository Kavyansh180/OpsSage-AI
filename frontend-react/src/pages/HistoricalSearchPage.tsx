import React, { useState } from 'react';
import { Search, BookOpen, ShieldCheck, Sparkles, Filter, Sliders } from 'lucide-react';
import { knowledgeService } from '../services/knowledgeService';
import { KnowledgeDocument } from '../types/knowledge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorBanner } from '../components/common/ErrorBanner';

export const HistoricalSearchPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [serviceName, setServiceName] = useState('');
  const [topK, setTopK] = useState(5);
  const [minSim, setMinSim] = useState(0.5);

  const [results, setResults] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setSearched(true);

    try {
      const data = await knowledgeService.searchKnowledge({
        query: query.trim(),
        service_name: serviceName.trim() || undefined,
        top_k: topK,
        min_similarity: minSim,
      });
      setResults(data.results || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Knowledge precedent search failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div>
        <h2 className="text-xl font-bold text-white tracking-tight flex items-center space-x-2">
          <BookOpen size={20} className="text-indigo-400" />
          <span>Historical Precedent Retrieval (RAG Explorer)</span>
        </h2>
        <p className="text-xs text-dark-muted">
          Semantic vector similarity search across past verified resolutions and incident knowledge
        </p>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Search & Filter Form */}
      <form
        onSubmit={handleSearch}
        className="bg-dark-surface border border-dark-border rounded-xl p-5 space-y-4"
      >
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1.5">
            Diagnostic Symptom or Failure Query
          </label>
          <div className="relative">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-muted"
            />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Database connection pool exhausted on worker node during high checkout volume..."
              required
              className="w-full bg-dark-bg border border-dark-border rounded-lg pl-9 pr-3 py-2.5 text-xs text-white focus:outline-none focus:border-indigo-500 placeholder-dark-muted"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-dark-border/60">
          {/* Service Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-dark-muted uppercase mb-1 flex items-center space-x-1">
              <Filter size={11} />
              <span>Microservice Filter (Optional)</span>
            </label>
            <input
              type="text"
              value={serviceName}
              onChange={(e) => setServiceName(e.target.value)}
              placeholder="e.g. checkout-service"
              className="w-full bg-dark-bg border border-dark-border rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500 placeholder-dark-muted"
            />
          </div>

          {/* Top Results Slider */}
          <div>
            <div className="flex justify-between text-[11px] font-semibold text-dark-muted uppercase mb-1">
              <span className="flex items-center space-x-1">
                <Sliders size={11} />
                <span>Top Results Limit</span>
              </span>
              <span className="text-white font-mono">{topK}</span>
            </div>
            <input
              type="range"
              min="1"
              max="10"
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value, 10))}
              className="w-full h-1 bg-dark-border rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />
            <div className="flex justify-between text-[10px] text-dark-muted mt-1">
              <span>1</span>
              <span>5</span>
              <span>10</span>
            </div>
          </div>

          {/* Similarity Threshold Slider */}
          <div>
            <div className="flex justify-between text-[11px] font-semibold text-dark-muted uppercase mb-1">
              <span>Min Cosine Similarity</span>
              <span className="text-white font-mono">{(minSim * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.05"
              value={minSim}
              onChange={(e) => setMinSim(parseFloat(e.target.value))}
              className="w-full h-1 bg-dark-border rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />
            <div className="flex justify-between text-[10px] text-dark-muted mt-1">
              <span>10%</span>
              <span>50%</span>
              <span>90%</span>
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-bold tracking-wide transition-all shadow flex items-center space-x-2"
          >
            <Search size={14} />
            <span>{loading ? 'Searching Vector Space...' : 'Retrieve Precedents'}</span>
          </button>
        </div>
      </form>

      {/* Results */}
      {loading ? (
        <LoadingSpinner label="Searching 384-dimensional vector embeddings..." />
      ) : searched && results.length === 0 ? (
        <EmptyState
          title="No Historical Precedents Matched"
          description="Try reducing the minimum similarity score slider or generalizing the query symptoms."
        />
      ) : (
        <div className="space-y-4">
          {results.length > 0 && (
            <div className="text-xs text-dark-muted">
              Found <strong className="text-white">{results.length}</strong> matching
              precedent{results.length === 1 ? '' : 's'}:
            </div>
          )}

          {results.map((doc) => (
            <div
              key={doc.knowledge_id || doc.id}
              className="bg-dark-surface border border-dark-border rounded-xl p-5 space-y-3 hover:border-slate-600 transition-all shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-xs font-bold text-indigo-400 bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-800/40">
                      {doc.source_incident_id}
                    </span>
                    {doc.score !== undefined && (
                      <span className="text-xs font-bold px-2 py-0.5 rounded bg-slate-800 text-emerald-400 border border-slate-700">
                        Score: {(doc.score * 100).toFixed(1)}%
                      </span>
                    )}
                    {doc.has_verified_resolution ? (
                      <span className="inline-flex items-center text-[10px] font-semibold text-emerald-300 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/50">
                        <ShieldCheck size={12} className="mr-1 text-emerald-400" />
                        Confirmed Resolution
                      </span>
                    ) : (
                      <span className="inline-flex items-center text-[10px] font-semibold text-purple-300 bg-purple-950/60 px-2 py-0.5 rounded border border-purple-800/50">
                        <Sparkles size={12} className="mr-1 text-purple-400" />
                        AI Hypothesis
                      </span>
                    )}
                  </div>
                  <h3 className="text-base font-bold text-white tracking-tight">{doc.title}</h3>
                  <div className="text-xs text-dark-muted">
                    Service: <strong className="text-slate-200">{doc.service_name}</strong> &middot;{' '}
                    Environment: <strong className="text-slate-200">{doc.environment}</strong>
                  </div>
                </div>
              </div>

              {doc.diagnostic_summary && (
                <p className="text-xs text-slate-300 leading-relaxed bg-dark-bg p-3 rounded-lg border border-dark-border">
                  {doc.diagnostic_summary}
                </p>
              )}

              {doc.confirmed_resolution && (
                <div className="p-3 bg-emerald-950/30 border border-emerald-800/40 rounded-lg text-xs space-y-1 text-emerald-200">
                  <span className="font-bold uppercase tracking-wider text-emerald-400 text-[10px] block">
                    Verified Remediation Applied
                  </span>
                  <p>{doc.confirmed_resolution}</p>
                </div>
              )}

              {doc.historical_analysis?.probable_root_cause && (
                <div className="p-3 bg-purple-950/30 border border-purple-800/40 rounded-lg text-xs space-y-1 text-purple-200">
                  <span className="font-bold uppercase tracking-wider text-purple-400 text-[10px] block">
                    Past AI Hypothesis
                  </span>
                  <p>{doc.historical_analysis.probable_root_cause}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
