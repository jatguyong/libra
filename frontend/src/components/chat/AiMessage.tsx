/**
 * AiMessage — renders a single LLM response with typewriter animation,
 * variant navigation, copy/redo actions, and the "Explanation" button.
 */

import { useState, useRef, useEffect } from 'react';
import { Copy, RefreshCw, ChevronLeft, ChevronRight, AlertTriangle } from 'lucide-react';
import ThinkingProcess from '../ThinkingProcess';
import { ChatMarkdown } from './MarkdownRenderer';
import type { Message, ExplanationData } from '../../lib/types';

interface AiMessageProps {
  message: Message;
  onRedo: (id: string) => void;
  isFinished: boolean;
  onExplanationClick: (data: ExplanationData) => void;
}

export default function AiMessage({ message, onRedo, isFinished, onExplanationClick }: AiMessageProps) {
  const [copied, setCopied] = useState(false);

  // ── Variant navigation ──────────────────────────────────────────
  const variants = message.alternativeContents
    ? [...message.alternativeContents, message.content]
    : [message.content];

  const [viewIndex, setViewIndex] = useState(variants.length - 1);

  useEffect(() => {
    setViewIndex(variants.length - 1);
  }, [variants.length]);

  const currentDisplayContent = variants[viewIndex] || '';

  // ── Typewriter effect ───────────────────────────────────────────
  const hasAnimated = useRef(false);
  const [revealedWordCount, setRevealedWordCount] = useState<number | null>(null);

  useEffect(() => {
    // Skip animation if already played, content is empty, or viewing an older variant
    if (hasAnimated.current || !currentDisplayContent || viewIndex !== variants.length - 1) {
      setRevealedWordCount(null);
      return;
    }

    const words = currentDisplayContent.split(/(\s+)/); // preserve whitespace tokens
    const totalTokens = words.length;
    setRevealedWordCount(0);

    const WORDS_PER_TICK = 2;
    const INTERVAL_MS = 30;

    const timer = setInterval(() => {
      setRevealedWordCount(prev => {
        const next = (prev ?? 0) + WORDS_PER_TICK;
        if (next >= totalTokens) {
          clearInterval(timer);
          hasAnimated.current = true;
          return null; // null = show full content
        }
        return next;
      });
    }, INTERVAL_MS);

    return () => clearInterval(timer);
  }, [currentDisplayContent, viewIndex, variants.length]);

  const shouldAnimate = !hasAnimated.current && Boolean(currentDisplayContent) && viewIndex === variants.length - 1;

  const textToRender = revealedWordCount === null
    ? (shouldAnimate ? '' : currentDisplayContent)
    : currentDisplayContent.split(/(\s+)/).slice(0, revealedWordCount).join('');

  // ── Actions ─────────────────────────────────────────────────────
  const handleCopy = () => {
    navigator.clipboard.writeText(currentDisplayContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // ── Guard: hide while streaming until first content arrives ─────
  if (!currentDisplayContent && !isFinished) return null;

  // ── Render ──────────────────────────────────────────────────────
  return (
    <div className="flex w-full justify-start">
      <div className="w-full rounded-2xl px-5 py-4 font-inter text-[15px] leading-relaxed bg-transparent text-white/90">

        {/* Thinking-process header */}
        <div className="mb-6 -ml-5">
          <ThinkingProcess isFinished={true} fallback={message.explanationData?.fallback} />
        </div>

        {/* Message body */}
        <div className="font-inter text-[15px] leading-relaxed w-full text-[#DEE1E5]">
          <ChatMarkdown>{textToRender.replace(/<br\s*\/?>/gi, '\n')}</ChatMarkdown>
        </div>

        {/* Action bar — only shown once generation finishes */}
        {isFinished && (
          <div className="mt-6 flex items-center gap-1 text-white/40">

            {/* Variant navigation arrows */}
            {variants.length > 1 && (
              <div className="flex items-center gap-1 mr-1 select-none text-xs font-medium">
                <button
                  onClick={() => setViewIndex(i => Math.max(0, i - 1))}
                  disabled={viewIndex === 0}
                  className={`p-1 rounded-md transition-colors ${viewIndex === 0 ? 'opacity-40' : 'hover:bg-white/30 hover:text-white cursor-pointer'}`}
                >
                  <ChevronLeft size={18} />
                </button>
                <span className="w-8 text-sm font-inter font-light text-center">
                  {viewIndex + 1}/{variants.length}
                </span>
                <button
                  onClick={() => setViewIndex(i => Math.min(variants.length - 1, i + 1))}
                  disabled={viewIndex === variants.length - 1}
                  className={`p-1 rounded-md transition-colors ${viewIndex === variants.length - 1 ? 'opacity-40' : 'hover:bg-white/30 hover:text-white cursor-pointer'}`}
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            )}

            {/* Copy */}
            <Tooltip label={copied ? 'Copied!' : 'Copy'}>
              <button onClick={handleCopy} className="p-1.5 hover:text-white hover:bg-white/10 rounded-md transition-colors cursor-pointer">
                <Copy size={18} />
              </button>
            </Tooltip>

            {/* Redo */}
            <Tooltip label="Redo response">
              <button onClick={() => onRedo(message.id)} className="p-1.5 hover:text-white hover:bg-white/10 rounded-md transition-colors cursor-pointer">
                <RefreshCw size={18} />
              </button>
            </Tooltip>

            {/* Tuned LLM warning */}
            {message.explanationData?.fallback === 'tuned' && (
              <Tooltip label="This response is not Prolog verified and relies solely on the LLM's parametric memory.">
                <div className="p-1.5 text-amber-500/80 hover:text-amber-400 rounded-md transition-colors cursor-help ml-1">
                  <AlertTriangle size={18} />
                </div>
              </Tooltip>
            )}

            {/* Explanation button */}
            {message.explanationData && (
              <button
                onClick={() => onExplanationClick(message.explanationData!)}
                className="text-base font-inter font-light text-white/40 hover:text-white/80 transition-colors ml-1 cursor-pointer"
              >
                Explanation
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tooltip helper ──────────────────────────────────────────────────

function Tooltip({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="relative group/tooltip flex items-center justify-center">
      {children}
      <div className="absolute bottom-full mb-2 bg-[#1a1523] text-white/80 text-xs px-2 py-1 rounded border border-white/10 opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all whitespace-nowrap z-10 pointer-events-none">
        {label}
      </div>
    </div>
  );
}
