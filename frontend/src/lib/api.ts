import { expireSession, getToken } from './auth';

/** Typed client for the NecroMARC API. The only module that calls `fetch`. */

export const DEFAULT_TIMEOUT_MS = 30_000;
export const DEFAULT_RESURRECT_TIMEOUT_MS = 120_000;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  /** Seconds from the Retry-After header, or null when absent or invalid. */
  readonly retryAfter: number | null;
  /** Extra sibling keys of the error envelope (e.g. `results`, `errors`). */
  readonly body: Record<string, unknown> | null;
  constructor(
    status: number,
    code: string,
    message: string,
    retryAfter: number | null = null,
    body: Record<string, unknown> | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
    this.body = body;
  }
  get i18nKey(): string {
    return errorKey(this.code);
  }
}

/** Map an `error.code` to an i18n key. */
export function errorKey(code: string | null | undefined): string {
  return code ? `error.${code}` : 'error.unknown';
}

function env(): Record<string, string | undefined> {
  return (import.meta.env ?? {}) as unknown as Record<string, string | undefined>;
}

export function apiBase(): string {
  return (env().PUBLIC_API_URL ?? '').replace(/\/+$/, '');
}

export function resurrectTimeoutMs(): number {
  const n = Number(env().PUBLIC_RESURRECT_TIMEOUT_MS);
  return Number.isInteger(n) && n > 0 ? n : DEFAULT_RESURRECT_TIMEOUT_MS;
}

export function parseRetryAfter(value: string | null): number | null {
  if (value === null || !/^\s*\d+\s*$/.test(value)) return null;
  return parseInt(value, 10);
}

interface RequestOptions {
  method?: 'GET' | 'POST';
  query?: Record<string, string | number | undefined | null>;
  json?: unknown;
  form?: FormData;
  auth?: boolean;
  timeoutMs?: number;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v));
  }
  const qs = params.toString();
  return `${apiBase()}${path}${qs ? `?${qs}` : ''}`;
}

async function errorFrom(res: Response): Promise<ApiError> {
  const retryAfter = parseRetryAfter(res.headers.get('Retry-After'));
  let code = 'UNKNOWN';
  let message = `HTTP ${res.status}`;
  let body: Record<string, unknown> | null = null;
  try {
    const data: unknown = await res.json();
    if (data && typeof data === 'object') {
      const { error, ...rest } = data as Record<string, unknown>;
      if (error && typeof error === 'object') {
        const e = error as Record<string, unknown>;
        if (typeof e.code === 'string') code = e.code;
        if (typeof e.message === 'string') message = e.message;
      }
      body = rest;
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, code, message, retryAfter, body);
}

async function send(path: string, opts: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {};
  if (opts.auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, opts.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const onAbort = () => controller.abort();
  opts.signal?.addEventListener('abort', onAbort);
  if (opts.signal?.aborted) controller.abort();

  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), {
      method: opts.method ?? 'GET',
      headers,
      body,
      signal: controller.signal,
    });
  } catch (e) {
    if (timedOut) throw new ApiError(0, 'TIMEOUT', 'Request timed out');
    if (opts.signal?.aborted) throw e;
    throw new ApiError(0, 'NETWORK_ERROR', 'Network error');
  } finally {
    clearTimeout(timer);
    opts.signal?.removeEventListener('abort', onAbort);
  }

  if (!res.ok) {
    if (res.status === 401 && opts.auth) expireSession();
    throw await errorFrom(res);
  }
  return res;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const res = await send(path, opts);
  return (await res.json()) as T;
}

// ---- Types -----------------------------------------------------------------

export type Field =
  | { tag: string; data: string; ai?: boolean }
  | { tag: string; ind1?: string; ind2?: string; subfields: [string, string][]; ai?: boolean };
export interface Anomaly {
  kind: 'encoding' | 'structural';
  code: string;
  message: string;
  tag?: string | null;
}
export interface RawRecord {
  leader: string | null;
  fields: Field[];
  anomalies?: Anomaly[];
}
export interface DecayEntry {
  rule: string;
  points: number;
}
export interface Decay {
  score: number;
  breakdown: DecayEntry[];
}
export interface RecordSummary {
  id: string;
  title: string | null;
  author: string | null;
  year: number | null;
  status: 'decayed' | 'resurrected' | 'failed';
  decay_score: number;
  vitality_score: number | null;
  subjects: string[];
  source: string;
  control_number: string;
  created_at?: string;
}
export interface RecordDetail {
  id: string;
  source: string;
  control_number: string;
  status: RecordSummary['status'];
  summary: RecordSummary;
  raw: RawRecord;
  healed: RawRecord | null;
  decay: Decay;
  vitality_score: number | null;
  resurrection: {
    healed_summary: string;
    inferred_subjects: string[];
    normalized_year: number | null;
    language_name: string;
    json_ld: Record<string, unknown>;
  } | null;
  has_embedding: boolean;
  failure_reason: string | null;
  created_at: string;
}
export interface LoginResponse {
  token: string;
  token_type: 'Bearer';
  expires_in: number;
}
export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}
export interface RecordsPage {
  items: RecordSummary[];
  total: number;
  page: number;
  page_size: number;
}
export interface RecordsQuery {
  page?: number;
  page_size?: number;
  q?: string;
  title?: string;
  author?: string;
  era_from?: number;
  era_to?: number;
  topic?: string;
  status?: RecordSummary['status'];
}
export interface ScoredSummary {
  summary: RecordSummary;
  similarity: number;
}
export interface SimilarResponse {
  record_id: string;
  has_embedding: boolean;
  results: ScoredSummary[];
}
export interface GraphResponse {
  elements: {
    nodes: { data: { id: string; label: string; kind: string } }[];
    edges: {
      data: { id: string; source: string; target: string; edgeType: string; weight: number };
    }[];
  };
  meta: { records: number; truncated: boolean };
}
export interface SemanticSearchResponse {
  query: string;
  results: ScoredSummary[];
}
export interface ParsedItem {
  index: number;
  record: RawRecord;
  decay: Decay;
  title?: string | null;
  control_number?: string | null;
}
export interface UploadResponse {
  records: ParsedItem[];
  errors: { code: string; message: string; byte_offset: number }[];
}
export type ResurrectResult =
  | { index: number; status: 'success'; id: string; record: RecordDetail; embedding_stored: boolean }
  | { index: number; status: 'failure'; error: { code: string; message: string } };
export interface ResurrectResponse {
  results: ResurrectResult[];
  summary: { submitted: number; succeeded: number; failed: number };
}
export interface TombResponse {
  filename: string;
  records: { index: number; record: RawRecord; decay: Decay }[];
  count: number;
}
export type ExportFormat = 'mrc' | 'marcxml' | 'jsonld';

// ---- Endpoints -------------------------------------------------------------

export const health = (): Promise<HealthResponse> => request('/health');

export const login = (username: string, password: string): Promise<LoginResponse> =>
  request('/auth/login', { method: 'POST', json: { username, password } });

export const listRecords = (q: RecordsQuery = {}): Promise<RecordsPage> =>
  request('/records', { query: { ...q } });

export const getRecord = (id: string): Promise<RecordDetail> =>
  request(`/records/${encodeURIComponent(id)}`);

export const getSimilar = (id: string, limit?: number): Promise<SimilarResponse> =>
  request(`/records/${encodeURIComponent(id)}/similar`, { query: { limit } });

/** URL for a download link; the export route needs no authentication. */
export const exportUrl = (id: string, format: ExportFormat): string =>
  buildUrl(`/records/${encodeURIComponent(id)}/export`, { format });

export async function exportRecord(
  id: string,
  format: ExportFormat,
): Promise<{ blob: Blob; filename: string | null }> {
  const res = await send(`/records/${encodeURIComponent(id)}/export`, { query: { format } });
  const cd = res.headers.get('Content-Disposition');
  const m = cd ? /filename="?([^";]+)"?/.exec(cd) : null;
  return { blob: await res.blob(), filename: m ? m[1] : null };
}

export const getGraph = (limit?: number): Promise<GraphResponse> =>
  request('/graph', { query: { limit } });

export const semanticSearch = (
  query: string,
  limit?: number,
  signal?: AbortSignal,
): Promise<SemanticSearchResponse> =>
  request('/search/semantic', {
    method: 'POST',
    auth: true,
    json: limit === undefined ? { query } : { query, limit },
    signal,
  });

export const uploadMrc = (file: Blob, filename = 'upload.mrc'): Promise<UploadResponse> => {
  const form = new FormData();
  form.append('file', file, filename);
  return request('/upload-mrc', { method: 'POST', auth: true, form });
};

/** Uses PUBLIC_RESURRECT_TIMEOUT_MS (default 120000) as its timeout (11.10). */
export const resurrect = (
  records: RawRecord[],
  signal?: AbortSignal,
): Promise<ResurrectResponse> =>
  request('/resurrect', {
    method: 'POST',
    auth: true,
    json: { records },
    timeoutMs: resurrectTimeoutMs(),
    signal,
  });

export const getTomb = (): Promise<TombResponse> => request('/samples/tomb');
