/**
 * API communication utilities for the Libra frontend.
 *
 * Single source of truth for the backend URL and the SSE streaming logic.
 */

import type { ExplanationData } from './types';

/** Backend base URL — configurable via VITE_API_URL env var at build time. */
export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';

// ── Helpers ─────────────────────────────────────────────────────────

/** Map raw API response data into a typed ExplanationData object. */
export function parseExplanationData(data: Record<string, unknown>): ExplanationData {
  return {
    explainer_output: (data.explainer_output as string) || '',
    prolog_explanation: (data.prolog_explanation as string) || '',
    database: (data.database as string) || '',
    query: (data.query as string) || '',
    prolog_query: (data.prolog_query as string) || '',
    contexts: (data.contexts as string[] | string) || [],
    condensed_context: (data.condensed_context as string) || '',
    fallback: (data.fallback as string) || 'unknown',
    prolog_error: (data.prolog_error as string) || null,
    logprobs: (data.logprobs as ExplanationData['logprobs']) || [],
    semantic_entropy: data.semantic_entropy as number | undefined,
    hallucination_flag: data.hallucination_flag as string | undefined,
  };
}

// ── SSE streaming ───────────────────────────────────────────────────

export interface StreamChatCallbacks {
  /** Called when the backend reports a pipeline step update. */
  onStep: (step: number, fallback?: string) => void;
  /** Called when the final result arrives. */
  onResult: (data: Record<string, unknown>, explanation: ExplanationData) => void;
}

/**
 * Open an SSE connection to `/api/chat`, parsing events as they arrive.
 *
 * Throws on network errors or backend‐reported pipeline errors.
 */
export async function streamChat(
  payload: object,
  { onStep, onResult }: StreamChatCallbacks,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.body) throw new Error('No response body');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';

    for (const part of parts) {
      if (!part.startsWith('data: ')) continue;

      const eventData = JSON.parse(part.slice(6));

      if (eventData.type === 'step') {
        onStep(eventData.step, eventData.fallback);
      } else if (eventData.type === 'result') {
        const data = eventData.data;
        if (data.error) throw new Error(data.details || data.error);
        onResult(data, parseExplanationData(data));
      } else if (eventData.type === 'error') {
        throw new Error(eventData.error || 'Unknown pipeline error');
      }
    }
  }
}
