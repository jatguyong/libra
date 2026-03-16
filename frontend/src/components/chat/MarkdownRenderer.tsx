/**
 * Shared ReactMarkdown renderer with consistent styling.
 *
 * Eliminates the 5× copy-pasted component overrides throughout the app.
 * Two variants are exported:
 *   - ChatMarkdown  — for main AI message text (slightly larger)
 *   - PaneMarkdown  — for explanation pane sections (slightly smaller)
 */

import ReactMarkdown from 'react-markdown';

// ── Component override maps ─────────────────────────────────────────

const chatComponents = {
  p: ({ children }: { children?: React.ReactNode }) => <p className="mb-4 last:mb-0">{children}</p>,
  ul: ({ children }: { children?: React.ReactNode }) => <ul className="list-disc pl-5 mb-4 space-y-1">{children}</ul>,
  ol: ({ children }: { children?: React.ReactNode }) => <ol className="list-decimal pl-5 mb-4 space-y-1">{children}</ol>,
  li: ({ children }: { children?: React.ReactNode }) => <li className="mb-1">{children}</li>,
  strong: ({ children }: { children?: React.ReactNode }) => <strong className="font-bold text-[#DEE1E5]">{children}</strong>,
  em: ({ children }: { children?: React.ReactNode }) => <em className="italic text-[#DEE1E5]">{children}</em>,
  h1: ({ children }: { children?: React.ReactNode }) => <h1 className="text-2xl font-bold mt-5 mb-3 text-[#DEE1E5]">{children}</h1>,
  h2: ({ children }: { children?: React.ReactNode }) => <h2 className="text-xl font-bold mt-5 mb-3 text-[#DEE1E5]">{children}</h2>,
  h3: ({ children }: { children?: React.ReactNode }) => <h3 className="text-lg font-bold mt-4 mb-2 text-[#DEE1E5]">{children}</h3>,
};

const paneComponents = {
  p: ({ children }: { children?: React.ReactNode }) => <p className="mb-3 last:mb-0">{children}</p>,
  ul: ({ children }: { children?: React.ReactNode }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
  ol: ({ children }: { children?: React.ReactNode }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
  li: ({ children }: { children?: React.ReactNode }) => <li className="mb-1">{children}</li>,
  strong: ({ children }: { children?: React.ReactNode }) => <strong className="font-bold text-white/90">{children}</strong>,
  em: ({ children }: { children?: React.ReactNode }) => <em className="italic">{children}</em>,
  h1: ({ children }: { children?: React.ReactNode }) => <h1 className="text-lg font-bold mt-4 mb-2 text-white/90">{children}</h1>,
  h2: ({ children }: { children?: React.ReactNode }) => <h2 className="text-base font-bold mt-4 mb-2 text-white/90">{children}</h2>,
  h3: ({ children }: { children?: React.ReactNode }) => <h3 className="text-sm font-bold mt-3 mb-1 text-white/90">{children}</h3>,
};

const paneCompactComponents = {
  p: ({ children }: { children?: React.ReactNode }) => <p className="mb-1 last:mb-0">{children}</p>,
  ul: ({ children }: { children?: React.ReactNode }) => <ul className="list-disc pl-4 space-y-0.5">{children}</ul>,
  li: ({ children }: { children?: React.ReactNode }) => <li className="mb-0.5">{children}</li>,
  strong: ({ children }: { children?: React.ReactNode }) => <strong className="font-bold text-white/90">{children}</strong>,
};

// ── Exported components ─────────────────────────────────────────────

interface MarkdownProps {
  children: string;
}

/** Full-width markdown block for AI chat messages. */
export function ChatMarkdown({ children }: MarkdownProps) {
  return (
    <ReactMarkdown components={chatComponents}>
      {children}
    </ReactMarkdown>
  );
}

/** Markdown block for explanation pane content. */
export function PaneMarkdown({ children }: MarkdownProps) {
  return (
    <ReactMarkdown components={paneComponents}>
      {children}
    </ReactMarkdown>
  );
}

/** Compact markdown for condensed-context sections inside the pane. */
export function PaneCompactMarkdown({ children }: MarkdownProps) {
  return (
    <ReactMarkdown components={paneCompactComponents}>
      {children}
    </ReactMarkdown>
  );
}
