import React from 'react';
import {
  Sparkles,
  AlertTriangle,
  FileText,
  ListChecks,
  CheckCircle2,
  Clock,
  Layers,
  Cpu,
} from 'lucide-react';
import { Analysis } from '../../types/analysis';
import { ConfidenceBadge } from '../common/ConfidenceBadge';

interface RCARunCardProps {
  analysis: Analysis;
  index: number;
}

export const RCARunCard: React.FC<RCARunCardProps> = ({ analysis, index }) => {
  return (
    <div className="bg-dark-surface border border-dark-border rounded-xl p-6 space-y-6 shadow-sm">
      {/* Run Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-dark-border pb-4">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
            <Sparkles size={18} />
          </div>
          <div>
            <h4 className="text-sm font-bold text-white tracking-wide">
              Diagnostic Run #{index + 1} &middot;{' '}
              <span className="font-mono text-xs text-indigo-300">
                {analysis.analysis_id}
              </span>
            </h4>
            <div className="flex items-center space-x-3 text-[11px] text-dark-muted mt-0.5">
              <span className="flex items-center space-x-1">
                <Clock size={12} />
                <span>{new Date(analysis.created_at).toLocaleString()}</span>
              </span>
              <span className="flex items-center space-x-1 text-slate-300">
                <Cpu size={12} className="text-indigo-400" />
                <span>{analysis.model} ({analysis.provider})</span>
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <ConfidenceBadge confidence={analysis.confidence_level} />
          {analysis.rag_status && (
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
              RAG: {analysis.rag_status}
            </span>
          )}
        </div>
      </div>

      {/* Probable Root Cause Callout */}
      <div className="bg-rose-950/25 border-l-4 border-rose-500 p-4 rounded-r-lg space-y-1">
        <div className="flex items-center space-x-2 text-rose-400 text-xs font-bold uppercase tracking-wider">
          <AlertTriangle size={15} />
          <span>Formulated Probable Root Cause</span>
        </div>
        <p className="text-sm font-semibold text-white leading-relaxed">
          {analysis.probable_root_cause}
        </p>
      </div>

      {/* Narrative Explanation */}
      <div className="space-y-2">
        <h5 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center space-x-1.5">
          <FileText size={14} className="text-indigo-400" />
          <span>Failure Mechanism & Step-by-Step Explanation</span>
        </h5>
        <div className="bg-dark-bg border border-dark-border rounded-lg p-4 text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
          {analysis.explanation}
        </div>
      </div>

      {/* Supporting Evidence Logs */}
      {analysis.supporting_evidence && analysis.supporting_evidence.length > 0 && (
        <div className="space-y-2">
          <h5 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center space-x-1.5">
            <Layers size={14} className="text-blue-400" />
            <span>Supporting Evidence Logs ({analysis.supporting_evidence.length})</span>
          </h5>
          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {analysis.supporting_evidence.map((item, idx) => (
              <div
                key={idx}
                className="bg-black/60 border border-dark-border/80 rounded p-2.5 font-mono text-[11px] text-emerald-400/90 whitespace-pre-wrap break-all"
              >
                {item}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommended Remediation Actions */}
      {analysis.recommended_actions && analysis.recommended_actions.length > 0 && (
        <div className="space-y-2">
          <h5 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center space-x-1.5">
            <ListChecks size={14} className="text-emerald-400" />
            <span>Recommended Remediation Actions</span>
          </h5>
          <div className="bg-dark-bg border border-dark-border rounded-lg p-3 space-y-2">
            {analysis.recommended_actions.map((action, idx) => (
              <div key={idx} className="flex items-start space-x-2.5 text-xs text-slate-200">
                <CheckCircle2 size={15} className="text-emerald-400 shrink-0 mt-0.5" />
                <span>{action}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Historical Precedents Consulted via RAG */}
      {analysis.similar_incidents && analysis.similar_incidents.length > 0 && (
        <div className="space-y-2">
          <h5 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center space-x-1.5">
            <Sparkles size={14} className="text-amber-400" />
            <span>Historical Precedents Consulted (RAG Grounding)</span>
          </h5>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {analysis.similar_incidents.map((prec, idx) => (
              <div
                key={idx}
                className="bg-dark-bg border border-dark-border rounded-lg p-3 text-xs space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-indigo-400 font-bold">
                    {prec.source_incident_id}
                  </span>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                    Similarity: {(prec.similarity_score * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="font-medium text-slate-200">{prec.title}</p>
                {prec.confirmed_resolution && (
                  <p className="text-[11px] text-emerald-300/90 bg-emerald-950/30 p-2 rounded border border-emerald-800/30">
                    <strong>Confirmed Fix:</strong> {prec.confirmed_resolution}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Anti-Hallucination Disclaimer */}
      <div className="p-3 bg-amber-950/20 border border-amber-800/40 rounded-lg text-amber-300/80 text-[11px] leading-relaxed flex items-start space-x-2">
        <AlertTriangle size={15} className="shrink-0 mt-0.5 text-amber-400" />
        <span>
          <strong>Anti-Hallucination Policy:</strong> Diagnostic hypotheses are generated
          by Gemini from evidence logs and past incidents. They must be validated by an
          authorized human engineer before production change execution.
        </span>
      </div>
    </div>
  );
};
