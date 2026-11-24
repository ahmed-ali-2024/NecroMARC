// @vitest-environment happy-dom
// Sample Tomb flow on the real Uploader markup and script (Requirements 9.4, 20.6, 20.8).
import { randomUUID } from 'node:crypto';
import { readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TOKEN_KEY } from '../lib/auth';

const here = dirname(fileURLToPath(import.meta.url));
const temps: string[] = [];

async function mountUploader(): Promise<void> {
  const src = readFileSync(join(here, 'Uploader.astro'), 'utf8');
  const body = src.replace(/^---[\s\S]*?---\n/, '');
  const m = body.match(/^([\s\S]*?)<script>([\s\S]*)<\/script>\s*$/);
  if (!m) throw new Error('no script in Uploader');
  document.body.innerHTML = `<main id="page"><div data-terminal-log></div></main>${m[1]}`;
  const file = join(here, `.tmp-Uploader-${randomUUID()}.ts`);
  temps.push(file);
  writeFileSync(file, m[2]);
  await import(/* @vite-ignore */ file);
}

class MemStorage {
  m = new Map<string, string>();
  getItem(k: string) { return this.m.get(k) ?? null; }
  setItem(k: string, v: string) { this.m.set(k, v); }
  removeItem(k: string) { this.m.delete(k); }
}
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const rec = (cn: string) => ({
  leader: '00000nam a2200000 a 4500',
  fields: [{ tag: '001', data: cn }, { tag: '245', ind1: '1', ind2: '0', subfields: [['a', `Title ${cn}`]] }],
  anomalies: [],
});
const tomb = (n: number, remaining: number, total = 50) => ({
  filename: 'sample_pool.mrc',
  records: Array.from({ length: n }, (_, i) => ({
    index: i, record: rec(`necro-sample-${String(i + 1).padStart(3, '0')}`), decay: { score: 75, breakdown: [] },
  })),
  count: n, total, remaining, exhausted: remaining === 0,
});
const allDuplicates = {
  error: { code: 'BATCH_FAILED', message: 'The batch produced no successful results.' },
  results: [0, 1, 2, 3].map((index) => ({
    index, status: 'failure', error: { code: 'DUPLICATE_RESURRECTED', message: 'already' },
  })),
  summary: { submitted: 4, succeeded: 0, failed: 4 },
};

/** fetch mock routed by path; records the parsed JSON bodies of resurrect calls. */
function routes(tombBody: unknown, resurrectRes: () => Response) {
  const resurrectBodies: unknown[] = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/samples/tomb')) return json(200, tombBody);
    if (url.endsWith('/resurrect')) {
      resurrectBodies.push(JSON.parse(String(init?.body)));
      return resurrectRes();
    }
    return json(404, { error: { code: 'NOT_FOUND', message: 'x' } });
  });
  vi.stubGlobal('fetch', fetchMock);
  return { fetchMock, resurrectBodies };
}
const resurrectCalls = (f: ReturnType<typeof vi.fn>) =>
  f.mock.calls.filter(([u]) => String(u).endsWith('/resurrect')).length;

beforeEach(() => {
  vi.resetModules();
  vi.stubGlobal('sessionStorage', new MemStorage());
  vi.stubEnv('PUBLIC_API_URL', 'https://x.test/api/');
  sessionStorage.setItem(TOKEN_KEY, 'jwt');
});
afterEach(() => {
  for (const f of temps.splice(0)) rmSync(f, { force: true });
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  document.body.innerHTML = '';
  localStorage.clear();
});

describe('Sample Tomb', () => {
  it('sends source "sample" and shows the pool status', async () => {
    const { resurrectBodies } = routes(tomb(4, 46), () =>
      json(200, {
        results: [0, 1, 2, 3].map((index) => ({ index, status: 'success', id: `id${index}`, record: {}, embedding_stored: true })),
        summary: { submitted: 4, succeeded: 4, failed: 0 },
      }),
    );
    await mountUploader();
    $('up-tomb').click();
    await vi.waitFor(() => expect($('up-outcome').hidden).toBe(false));
    expect(resurrectBodies).toHaveLength(1);
    expect(resurrectBodies[0]).toMatchObject({ source: 'sample' });
    expect((resurrectBodies[0] as { records: unknown[] }).records).toHaveLength(4);
    // 46 were waiting; the 4 just resurrected leave 42.
    expect($('up-tomb-remaining').hidden).toBe(false);
    expect($('up-tomb-remaining').textContent).toContain('42 of 50');
    expect($('up-tomb-exhausted').hidden).toBe(true);
  });

  it('exhausted pool: message with links, and no resurrect request', async () => {
    const { fetchMock } = routes(tomb(0, 0), () => json(500, {}));
    await mountUploader();
    $('up-tomb').click();
    await vi.waitFor(() => expect($('up-tomb-exhausted').hidden).toBe(false));
    expect($('up-tomb-exhausted-text').textContent).toContain('All 50 records');
    expect($<HTMLAnchorElement>('up-tomb-archive').getAttribute('href')).toMatch(/\/$/);
    expect($<HTMLAnchorElement>('up-tomb-sources').getAttribute('href')).toBe('#marc-sources');
    expect(resurrectCalls(fetchMock)).toBe(0);
    expect($('up-tomb-remaining').hidden).toBe(true);
    expect($('up-error').hidden).toBe(true);
  });

  it('422 BATCH_FAILED renders one readable line per record', async () => {
    routes(tomb(4, 4), () => json(422, allDuplicates));
    await mountUploader();
    $('up-tomb').click();
    await vi.waitFor(() => expect($('up-outcome').hidden).toBe(false));
    const lines = [...$('up-outcome-list').querySelectorAll('li')].map((li) => li.textContent);
    expect(lines).toEqual([1, 2, 3, 4].map((i) => `Record ${i}: already resurrected earlier.`));
    expect($('up-summary').textContent).toBe('0 of 4 resurrected, 4 failed.');
    expect($('up-error').textContent).toContain('None of the 4 record(s) could be resurrected');
    expect(document.body.textContent).not.toMatch(/\berror\.[A-Z_]+/);
    // All 4 were already resurrected: the pool count reflects that.
    expect($('up-tomb-exhausted').hidden).toBe(false);
  });

  it('an unknown error or outcome code shows a generic message, never a raw key', async () => {
    routes(tomb(2, 10), () =>
      json(422, {
        error: { code: 'BATCH_FAILED', message: 'm' },
        results: [{ index: 0, status: 'failure', error: { code: 'SOMETHING_NEW', message: 'x' } },
                  { index: 1, status: 'failure', error: { code: 'DUPLICATE_RESURRECTED', message: 'x' } }],
        summary: { submitted: 2, succeeded: 0, failed: 2 },
      }),
    );
    await mountUploader();
    $('up-tomb').click();
    await vi.waitFor(() => expect($('up-outcome').hidden).toBe(false));
    const first = $('up-outcome-list').querySelector('li')!.textContent;
    expect(first).toBe('Record 1: could not be resurrected.');
    expect(document.body.textContent).not.toMatch(/\b(error|summon\.outcome)\.[A-Za-z_]+/);
  });

  it('a non-JSON or unknown top-level error falls back to error.unknown text', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) =>
      url.endsWith('/samples/tomb')
        ? new Response('<html>Bad gateway</html>', { status: 502 })
        : json(404, {})));
    await mountUploader();
    $('up-tomb').click();
    await vi.waitFor(() => expect($('up-error').hidden).toBe(false));
    expect($('up-error').textContent).toBe('Something went wrong.');
  });

  it('re-renders the pool and outcome lines in Arabic', async () => {
    routes(tomb(4, 4), () => json(422, allDuplicates));
    await mountUploader();
    $('up-tomb').click();
    await vi.waitFor(() => expect($('up-outcome').hidden).toBe(false));
    // Same module instance as the mounted script (modules are reset before each test).
    const { setLang } = await import('../i18n/i18n');
    setLang('ar');
    const first = $('up-outcome-list').querySelector('li')!.textContent ?? '';
    expect(first).toContain('سبق إحياؤه من قبل');
    expect($('up-tomb-exhausted-text').textContent).toContain('أُحيي جميع تسجيلات مخزون العينات');
  });
});
