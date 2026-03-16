/**
 * ExplanationPane — slide-out panel showing pipeline details for a selected response.
 *
 * Sections: pipeline badge, semantic entropy, logprobs, query,
 * GraphRAG sources (condensed context), explainability, Prolog details, Prolog error.
 */

import { motion } from 'framer-motion';
import { X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { PaneMarkdown, PaneCompactMarkdown } from './chat/MarkdownRenderer';
import type { ExplanationData, LogprobEntry } from '../lib/types';

interface ExplanationPaneProps {
  isOpen: boolean;
  onClose: () => void;
  data: ExplanationData | null;
}

export default function ExplanationPane({ isOpen, onClose, data }: ExplanationPaneProps) {
  return (
    <motion.div
      initial={false}
      animate={{ width: isOpen ? 384 : 0, opacity: isOpen ? 1 : 0 }}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
      className="h-full shrink-0 pointer-events-auto flex flex-col bg-[#0E0915] border-l border-white/10 overflow-hidden z-20"
    >
      <div className="w-[384px] h-full flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 shrink-0">
          <span className="font-space text-base font-normal tracking-widest mt-[2px] text-white">Explanation</span>
          <button onClick={onClose} className="text-white/50 hover:text-white transition-colors cursor-pointer">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
          {data ? (
            <>
              <PipelineBadge fallback={data.fallback} />
              <SemanticEntropySection data={data} />
              <LogprobsSection logprobs={data.logprobs} />
              <QuerySection query={data.query} />
              <GraphRAGSourcesSection data={data} />
              <ExplainabilitySection data={data} />
              <PrologDetailsSection data={data} />
              <PrologErrorSection error={data.prolog_error} />
            </>
          ) : (
            <p className="text-white/40 text-sm font-inter">
              Click "Explanation" on a response to view pipeline details.
            </p>
          )}
        </div>
      </div>
    </motion.div>
  );
}

// ── Sub-sections ────────────────────────────────────────────────────
//    Each section is a focused, readable component.

function PipelineBadge({ fallback }: { fallback: string }) {
  const config: Record<string, { classes: string; label: string }> = {
    'prolog-graphrag': { classes: 'bg-purple-500/20 text-purple-300 border-purple-500/30', label: '⚡ Prolog-GraphRAG' },
    graphrag: { classes: 'bg-blue-500/20 text-blue-300 border-blue-500/30', label: '🔍 GraphRAG Only' },
  };
  const { classes, label } = config[fallback] ?? { classes: 'bg-amber-500/20 text-amber-300 border-amber-500/30', label: '🧠 Tuned LLM' };

  return (
    <div>
      <span className={`inline-block px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase border ${classes}`}>
        {label}
      </span>
    </div>
  );
}

function SemanticEntropySection({ data }: { data: ExplanationData }) {
  if (data.semantic_entropy == null) return null;

  return (
    <div className="mb-4 bg-white/5 rounded-lg p-3 border border-white/10 flex flex-col gap-2">
      <div className="flex justify-between items-center">
        <span className="text-xs uppercase tracking-wider font-semibold text-white/50">Semantic Entropy</span>
        <span className="text-sm font-mono text-white/90 bg-black/30 px-2 py-0.5 rounded">
          {data.semantic_entropy!.toFixed(4)}
        </span>
      </div>
      {data.hallucination_flag && (
        <div className="flex justify-between items-center">
          <span className="text-xs uppercase tracking-wider font-semibold text-white/50">Confidence</span>
          <span className={`text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${
            data.hallucination_flag === 'likely_hallucination'
              ? 'bg-amber-500/20 text-amber-300'
              : 'bg-green-500/20 text-emerald-300'
          }`}>
            {data.hallucination_flag.replace('_', ' ')}
          </span>
        </div>
      )}
    </div>
  );
}

function LogprobsSection({ logprobs }: { logprobs: LogprobEntry[] }) {
  if (!logprobs || logprobs.length === 0) return null;

  return (
    <div className="mb-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-2">Token Log Probabilities</h3>
      <div className="bg-white/5 rounded-lg border border-white/10 max-h-48 overflow-y-auto p-2 space-y-1">
        {logprobs.map((lp, i) => {
          const token = lp.token || (typeof lp === 'string' ? lp : JSON.stringify(lp));
          const prob = typeof lp.logprob === 'number'
            ? lp.logprob.toFixed(4)
            : (typeof lp === 'number' ? (lp as number).toFixed(4) : 'N/A');
          return (
            <div key={i} className="flex justify-between items-center px-2 py-1 hover:bg-white/5 rounded">
              <span className="text-xs font-mono text-white/80 truncate max-w-[200px]">{token}</span>
              <span className="text-xs font-mono text-white/50">{prob}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function QuerySection({ query }: { query: string }) {
  if (!query) return null;

  return (
    <div className="mb-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-2">Query</h3>
      <div className="text-sm text-white/80 font-inter leading-relaxed">
        <PaneMarkdown>{query}</PaneMarkdown>
      </div>
    </div>
  );
}

function GraphRAGSourcesSection({ data }: { data: ExplanationData }) {
  const cc = data.condensed_context;
  const hasValidContext = cc && !cc.toLowerCase().includes('error during generation');
  const hasContexts = Array.isArray(data.contexts) && data.contexts.length > 0;

  if (!hasValidContext && !hasContexts) return null;

  return (
    <div className="mb-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-2">GraphRAG Sources</h3>

      {hasValidContext && <CondensedContextBlock text={cc} />}

      {hasContexts && (
        <div>
          <p className="text-xs text-white/40 mb-1">Retrieved Contexts ({(data.contexts as string[]).length})</p>
          <div className="space-y-4 max-h-64 overflow-y-auto pr-2 text-sm text-white/80 font-inter leading-relaxed">
            {(data.contexts as string[]).map((ctx, i) => (
              <PaneMarkdown key={i}>{ctx}</PaneMarkdown>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Splits the condensed context string by its **SECTION_NAME**: headers and
 * renders each as a styled card.  Falls back to plain markdown if headers are absent.
 */
function CondensedContextBlock({ text }: { text: string }) {
  const SECTION_KEYS = ['ATOMIC FACTS', 'CONDITIONAL RULES', 'EXCEPTIONS', 'LOGICAL GAPS'] as const;
  const pattern = /\*\*(ATOMIC FACTS|CONDITIONAL RULES|EXCEPTIONS|LOGICAL GAPS)\*\*:/g;

  const matches: { label: string; contentStart: number; headerStart: number }[] = [];
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null) {
    matches.push({ label: match[1], contentStart: match.index + match[0].length, headerStart: match.index });
  }

  if (matches.length === 0) {
    return (
      <div className="text-sm text-white/80 font-inter leading-relaxed mb-3">
        <ReactMarkdown>{text}</ReactMarkdown>
      </div>
    );
  }

  const sections: Record<string, string> = {};
  matches.forEach((m, i) => {
    const end = i + 1 < matches.length ? matches[i + 1].headerStart : text.length;
    sections[m.label] = text.slice(m.contentStart, end).trim();
  });

  return (
    <div className="space-y-2 mb-3">
      {SECTION_KEYS.map(key => {
        const content = sections[key];
        if (!content || content.toLowerCase() === 'none') return null;
        return (
          <div key={key} className="rounded-lg bg-white/5 px-3 py-2">
            <p className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-1">{key}</p>
            <div className="text-sm text-white/80 font-inter leading-relaxed">
              <PaneCompactMarkdown>{content}</PaneCompactMarkdown>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ExplainabilitySection({ data }: { data: ExplanationData }) {
  if (!data.explainer_output && !data.prolog_explanation) return null;

  return (
    <div className="mb-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-2">Explainability</h3>

      {data.explainer_output && (
        <div className="mb-3">
          <p className="text-xs text-white/40 mb-2">Explainer Output</p>
          <div className="text-sm text-white/80 font-inter leading-relaxed">
            <PaneMarkdown>{data.explainer_output}</PaneMarkdown>
          </div>
        </div>
      )}

      {data.prolog_explanation && (
        <div>
          <p className="text-xs text-white/40 mb-1">Prolog Explanation</p>
          <p className="text-sm text-white/80 font-inter leading-relaxed whitespace-pre-wrap bg-white/5 rounded-lg p-3 border border-white/5">
            {data.prolog_explanation}
          </p>
        </div>
      )}
    </div>
  );
}

function PrologDetailsSection({ data }: { data: ExplanationData }) {
  if (!data.database && !data.prolog_query) return null;

  return (
    <div className="mb-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50 mb-2">Prolog Details</h3>

      {data.prolog_query && (
        <div className="mb-3">
          <p className="text-xs text-white/40 mb-1">Prolog Query</p>
          <pre className="text-xs text-cyan-300/80 font-mono leading-relaxed whitespace-pre-wrap bg-white/5 rounded-lg p-3 border border-white/5">
            {data.prolog_query}
          </pre>
        </div>
      )}

      {data.database && (
        <div>
          <p className="text-xs text-white/40 mb-1">Database</p>
          <pre className="text-xs text-green-300/80 font-mono leading-relaxed whitespace-pre-wrap bg-white/5 rounded-lg p-3 border border-white/5 max-h-48 overflow-y-auto">
            {data.database}
          </pre>
        </div>
      )}
    </div>
  );
}

function PrologErrorSection({ error }: { error: string | null }) {
  if (!error) return null;

  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wider text-red-400/70 mb-2">Prolog Error</h3>
      <p className="text-sm text-red-300/80 font-inter leading-relaxed whitespace-pre-wrap bg-red-500/5 rounded-lg p-3 border border-red-500/10">
        {error}
      </p>
    </div>
  );
}
