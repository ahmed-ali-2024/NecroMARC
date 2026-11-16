import { ApiError } from './api';

/** Matches the backend MAX_UPLOAD_BYTES default (5 MiB). */
export const DEFAULT_MAX_UPLOAD_BYTES = 5_242_880;
export const MAX_BATCH_RECORDS = 5;
const RECORD_TERMINATOR = 0x1d;

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

/** Count ISO 2709 record terminators (0x1D); used to enforce the 5-record limit before upload. */
export function countRecords(bytes: Uint8Array): number {
  let n = 0;
  for (const b of bytes) if (b === RECORD_TERMINATOR) n++;
  return n;
}

export function validateRecordCount(count: number): UploadCheck {
  return count > MAX_BATCH_RECORDS ? { ok: false, errorKey: 'summon.error.too_many' } : { ok: true };
}

export interface ErrorView {
  key: string;
  params?: Record<string, number>;
  expired: boolean;
}

/** Map a failed upload or resurrect call to a localized message (401/413/422/429). */
export function summonErrorView(e: unknown): ErrorView {
  if (e instanceof ApiError) {
    if (e.status === 401) return { key: 'summon.error.session_expired', expired: true };
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
