/**
 * Shared TypeScript interfaces for the Libra frontend.
 */

/** A single token-level log probability from the LLM. */
export interface LogprobEntry {
  token: string;
  logprob: number;
}

/** Metadata returned alongside an LLM response from the pipeline. */
export interface ExplanationData {
  explainer_output: string;
  prolog_explanation: string;
  database: string;
  query: string;
  prolog_query?: string;
  contexts: string[] | string;
  condensed_context: string;
  fallback: string;
  prolog_error: string | null;
  logprobs: LogprobEntry[];
  semantic_entropy?: number;
  hallucination_flag?: string;
}

/** A single chat message (user or LLM). */
export interface Message {
  id: string;
  role: 'user' | 'llm';
  content: string;
  alternativeContents?: string[];
  explanationData?: ExplanationData;
}
