import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, errorKey, exportUrl, getRecord, listRecords, parseRetryAfter, resurrect, semanticSearch } from './api';
import { TOKEN_KEY, getToken, login, logout } from './auth';

class MemStorage {
  m = new Map<string, string>();
  getItem(k: string) { return this.m.get(k) ?? null; }
  setItem(k: string, v: string) { this.m.set(k, v); }
  removeItem(k: string) { this.m.delete(k); }
}

const events: string[] = [];
const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });

beforeEach(() => {
  events.length = 0;
  vi.stubGlobal('sessionStorage', new MemStorage());
  const target = new EventTarget();
  vi.stubGlobal('window', {
    dispatchEvent: (e: Event) => { events.push(e.type); return target.dispatchEvent(e); },
  });
  vi.stubEnv('PUBLIC_API_URL', 'https://x.test/api/');
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.useRealTimers();
});

describe('api client', () => {
  it('prefixes the base URL, builds the query and sends no auth for public calls', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'tok');
    const f = vi.fn().mockResolvedValue(json(200, { items: [] }));
    vi.stubGlobal('fetch', f);
    await listRecords({ page: 2, q: 'dune', title: undefined });
    const [url, init] = f.mock.calls[0];
    expect(url).toBe('https://x.test/api/records?page=2&q=dune');
    expect(init.headers.Authorization).toBeUndefined();
  });

  it('attaches the bearer token on protected calls', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'tok');
    const f = vi.fn().mockResolvedValue(json(200, { query: 'a', results: [] }));
    vi.stubGlobal('fetch', f);
    await semanticSearch('a');
    expect(f.mock.calls[0][1].headers.Authorization).toBe('Bearer tok');
    expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({ query: 'a' });
  });

  it('parses the error envelope', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(404, { error: { code: 'NOT_FOUND', message: 'nope' } })));
    const err = await getRecord('abc').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 404, code: 'NOT_FOUND', message: 'nope', i18nKey: 'error.NOT_FOUND' });
  });

  it('falls back to UNKNOWN for non-JSON errors and keeps sibling keys', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response('<html>', { status: 500 })));
    expect(await getRecord('a').catch((e) => e)).toMatchObject({ status: 500, code: 'UNKNOWN' });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(
      json(502, { error: { code: 'BATCH_FAILED', message: 'm' }, results: [1] })));
    const err = await resurrect([]).catch((e) => e);
    expect(err.body).toEqual({ results: [1] });
  });

  it('clears the token and dispatches auth:expired on 401 of a protected call', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'tok');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(401, { error: { code: 'UNAUTHENTICATED', message: 'x' } })));
    await expect(semanticSearch('a')).rejects.toMatchObject({ status: 401 });
    expect(getToken()).toBeNull();
    expect(events).toEqual(['auth:expired']);
  });

  it('does not expire the session on 401 of a public call', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'tok');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(401, { error: { code: 'X', message: 'x' } })));
    await expect(getRecord('a')).rejects.toBeInstanceOf(ApiError);
    expect(getToken()).toBe('tok');
    expect(events).toEqual([]);
  });

  it('reads Retry-After on 429', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      json(429, { error: { code: 'RATE_LIMITED', message: 'slow' } }, { 'Retry-After': '17' })));
    expect(await getRecord('a').catch((e) => e)).toMatchObject({ status: 429, retryAfter: 17 });
    expect(parseRetryAfter(null)).toBeNull();
    expect(parseRetryAfter('soon')).toBeNull();
  });

  it('times out with TIMEOUT using PUBLIC_RESURRECT_TIMEOUT_MS for resurrect', async () => {
    vi.useFakeTimers();
    vi.stubEnv('PUBLIC_RESURRECT_TIMEOUT_MS', '5000');
    vi.stubGlobal('fetch', vi.fn((_u: string, init: RequestInit) =>
      new Promise((_r, rej) => init.signal!.addEventListener('abort', () => rej(new DOMException('a', 'AbortError'))))));
    const p = resurrect([{ leader: null, fields: [] }]).catch((e) => e);
    await vi.advanceTimersByTimeAsync(4999);
    let settled = false;
    p.then(() => (settled = true));
    await Promise.resolve();
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(2);
    expect(await p).toMatchObject({ code: 'TIMEOUT' });
  });

  it('maps network failures to NETWORK_ERROR', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fail')));
    expect(await getRecord('a').catch((e) => e)).toMatchObject({ code: 'NETWORK_ERROR' });
  });

  it('builds export URLs and i18n keys', () => {
    expect(exportUrl('id1', 'marcxml')).toBe('https://x.test/api/records/id1/export?format=marcxml');
    expect(errorKey('RATE_LIMITED')).toBe('error.RATE_LIMITED');
    expect(errorKey(undefined)).toBe('error.unknown');
  });
});

describe('auth state', () => {
  it('stores the token and dispatches auth:changed on login', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(200, { token: 'jwt', token_type: 'Bearer', expires_in: 3600 })));
    expect(await login('u', 'p')).toEqual({ ok: true });
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe('jwt');
    expect(events).toEqual(['auth:changed']);
  });

  it('reports invalid credentials and rate limiting without storing a token', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json(401, { error: { code: 'INVALID_CREDENTIALS', message: 'm' } })));
    expect(await login('u', 'p')).toEqual({ ok: false, kind: 'invalid_credentials' });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(
      json(429, { error: { code: 'RATE_LIMITED', message: 'm' } }, { 'Retry-After': '30' })));
    expect(await login('u', 'p')).toEqual({ ok: false, kind: 'rate_limited', retryAfter: 30 });
    expect(getToken()).toBeNull();
    expect(events).toEqual([]);
  });

  it('logout clears the token and dispatches auth:changed', () => {
    sessionStorage.setItem(TOKEN_KEY, 'jwt');
    logout();
    expect(getToken()).toBeNull();
    expect(events).toEqual(['auth:changed']);
  });
});
