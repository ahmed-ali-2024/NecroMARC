import { ApiError } from './api';
import type { ResurrectResponse } from './api';
import { hasKey } from '../i18n/i18n';

/** Matches the backend MAX_UPLOAD_BYTES default (5 MiB). */
export const DEFAULT_MAX_UPLOAD_BYTES = 5_242_880;
export const MAX_BATCH_RECORDS = 5;

export function maxUploadBytes(): number {
  const raw = (import.meta.env as unknown as Record<string, string | undefined> | undefined)
    ?.PUBLIC_MAX_UPLOAD_BYTES;
  const n = Number(raw);
  return Number.isInteger(n) && n > 0 ? n : DEFAULT_MAX_UPLOAD_BYTES;
}

export type UploadCheck = { ok: true; errorKey?: undefined } | { ok: false; errorKey: string };

/** Client-side check run before any request: `.mrc` (case-insensitive), non-empty, within the size cap. */
export function validateUpload(
  file: { name: string; size: number },
  maxBytes: number = maxUploadBytes(),
): UploadCheck {
  if (!/\.mrc$/i.test(file.name)) return { ok: false, errorKey: 'summon.error.extension' };
  if (!(file.size > 0)) return { ok: false, errorKey: 'summon.error.empty' };
  if (file.size > maxBytes) return { ok: false, errorKey: 'summon.error.too_large' };
  return { ok: true };
}

export interface ErrorView {
  key: string;
  params?: Record<string, number>;
  expired: boolean;
}

/** i18n key for a per-record failure code; unknown codes get a generic message (Req 20.8). */
export function outcomeKey(code: string | null | undefined): string {
  const key = `summon.outcome.${code}`;
  return code && hasKey(key) ? key : 'summon.outcome.unknown';
}

/** Per-record results attached to a `422 BATCH_FAILED` body, or null for any other error. */
export function batchFailedBody(e: unknown): ResurrectResponse | null {
  if (!(e instanceof ApiError) || e.code !== 'BATCH_FAILED' || !e.body) return null;
  const { results, summary } = e.body as Partial<ResurrectResponse>;
  return Array.isArray(results) && summary ? { results, summary } : null;
}

/** Map a failed upload or resurrect call to a localized message (401/413/422/429). */
export function summonErrorView(e: unknown): ErrorView {
  if (e instanceof ApiError) {
    if (e.status === 401) return { key: 'summon.error.session_expired', expired: true };
    if (e.code === 'BATCH_FAILED') {
      const failed = batchFailedBody(e)?.summary.failed;
      return failed === undefined
        ? { key: 'error.BATCH_FAILED', expired: false }
        : { key: 'summon.error.batch_failed', params: { failed }, expired: false };
    }
    if (e.status === 413) return { key: 'summon.error.payload_too_large', expired: false };
    if (e.status === 422) return { key: 'summon.error.unparseable', expired: false };
    if (e.status === 429) {
      return e.retryAfter !== null
        ? { key: 'summon.error.rate_limited', params: { seconds: e.retryAfter }, expired: false }
        : { key: 'summon.error.rate_limited_unknown', expired: false };
    }
    return { key: e.i18nKey, expired: false };
  }
  return { key: 'error.unknown', expired: false };
}
