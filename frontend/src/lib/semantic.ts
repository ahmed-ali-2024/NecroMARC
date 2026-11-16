import { ApiError } from './api';

export const MIN_SEMANTIC_QUERY = 1;
export const MAX_SEMANTIC_QUERY = 1000;

export type QueryCheck = { ok: true; query: string } | { ok: false; errorKey: string };

/** Trim and validate a semantic query (1..1000 characters, counted as code points). */
export function validateSemanticQuery(raw: string): QueryCheck {
  const query = raw.trim();
  const len = Array.from(query).length;
  if (len < MIN_SEMANTIC_QUERY) return { ok: false, errorKey: 'semantic.error.empty' };
  if (len > MAX_SEMANTIC_QUERY) return { ok: false, errorKey: 'semantic.error.too_long' };
  return { ok: true, query };
}

export interface SemanticErrorView {
  key: string;
  params?: Record<string, number>;
  /** True when the Judge session is gone and the login prompt should show. */
  expired: boolean;
}

/** Map a failed semantic search to a localized message key. */
export function semanticErrorView(e: unknown): SemanticErrorView {
  if (e instanceof ApiError) {
    if (e.status === 401) return { key: 'semantic.error.session_expired', expired: true };
    if (e.status === 429) {
      return e.retryAfter !== null
        ? { key: 'semantic.error.rate_limited', params: { seconds: e.retryAfter }, expired: false }
        : { key: 'semantic.error.rate_limited_unknown', expired: false };
    }
    if (e.status === 502) return { key: 'semantic.error.upstream', expired: false };
    return { key: e.i18nKey, expired: false };
  }
  return { key: 'error.unknown', expired: false };
}

/** Similarity as a percentage string, e.g. 0.8734 -> "87%". */
export function formatSimilarity(s: number): string {
  const c = Math.min(1, Math.max(0, Number.isFinite(s) ? s : 0));
  return `${Math.round(c * 100)}%`;
}

export function chamberHref(base: string, id: string): string {
  return `${base.replace(/\/+$/, '')}/chamber/?id=${encodeURIComponent(id)}`;
}
