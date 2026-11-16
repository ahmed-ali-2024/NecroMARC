// @vitest-environment happy-dom
// Mounts the real .astro markup and runs its real inline <script> in happy-dom.
import { randomUUID } from 'node:crypto';
import { readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TOKEN_KEY, logout } from '../lib/auth';

const here = dirname(fileURLToPath(import.meta.url));
const temps: string[] = [];

async function mount(name: string, extraHtml = ''): Promise<void> {
  const src = readFileSync(join(here, `${name}.astro`), 'utf8');
  const body = src.replace(/^---[\s\S]*?---\n/, '');
  const m = body.match(/^([\s\S]*?)<script>([\s\S]*)<\/script>\s*$/);
  if (!m) throw new Error(`no script in ${name}`);
  const html = m[1].replace(/\{[A-Z_]+\}/g, '1000');
  document.body.innerHTML = `<main id="page">${extraHtml}<button id="opener">open</button></main>${html}`;
  const file = join(here, `.tmp-${name}-${randomUUID()}.ts`);
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
const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const tick = () => new Promise((r) => setTimeout(r, 0));
const key = (el: Element, k: string, shiftKey = false) =>
  el.dispatchEvent(new KeyboardEvent('keydown', { key: k, shiftKey, bubbles: true, cancelable: true }));

beforeEach(() => {
  vi.resetModules();
  vi.stubGlobal('sessionStorage', new MemStorage());
  vi.stubEnv('PUBLIC_API_URL', 'https://x.test/api/');
});
afterEach(() => {
  for (const f of temps.splice(0)) rmSync(f, { force: true });
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.useRealTimers();
  document.body.innerHTML = '';
});

describe('LoginModal', () => {
  const openModal = () =>
    window.dispatchEvent(new CustomEvent('login:open', { detail: { opener: $('opener') } }));

  it('opens with focus on username and inerts the page', async () => {
    await mount('LoginModal');
    expect($('login-modal').hidden).toBe(true);
    $('opener').focus();
    openModal();
    expect($('login-modal').hidden).toBe(false);
    expect(document.activeElement).toBe($('login-username'));
    expect($('page').hasAttribute('inert')).toBe(true);
  });

  it('traps Tab and Shift+Tab inside the dialog', async () => {
    await mount('LoginModal');
    openModal();
    $('login-submit').focus();
    key($('login-submit'), 'Tab');
    expect(document.activeElement).toBe($('login-username'));
    key($('login-username'), 'Tab', true);
    expect(document.activeElement).toBe($('login-submit'));
  });

  it('Escape closes, clears values, and restores focus to the opener', async () => {
    await mount('LoginModal');
    $('opener').focus();
    openModal();
    $<HTMLInputElement>('login-username').value = 'u';
    $<HTMLInputElement>('login-password').value = 'p';
    key($('login-username'), 'Escape');
    expect($('login-modal').hidden).toBe(true);
    expect($<HTMLInputElement>('login-username').value).toBe('');
    expect($<HTMLInputElement>('login-password').value).toBe('');
    expect($('page').hasAttribute('inert')).toBe(false);
    expect(document.activeElement).toBe($('opener'));
  });

  it('401 shows an error, clears the password and keeps the modal open', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(401, { error: { code: 'INVALID_CREDENTIALS', message: 'm' } })));
    await mount('LoginModal');
    openModal();
    $<HTMLInputElement>('login-username').value = 'u';
    $<HTMLInputElement>('login-password').value = 'bad';
    $<HTMLFormElement>('login-form').dispatchEvent(new Event('submit', { cancelable: true }));
    await vi.waitFor(() => expect($('login-error').hidden).toBe(false));
    expect($('login-error').textContent).not.toBe('');
    expect($<HTMLInputElement>('login-password').value).toBe('');
    expect($('login-modal').hidden).toBe(false);
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(($('login-submit') as HTMLButtonElement).disabled).toBe(false);
  });

  it('429 disables submit with a countdown and re-enables afterwards', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      json(429, { error: { code: 'RATE_LIMITED', message: 'm' } }, { 'Retry-After': '2' })));
    await mount('LoginModal');
    openModal();
    $<HTMLInputElement>('login-username').value = 'u';
    $<HTMLInputElement>('login-password').value = 'p';
    $<HTMLFormElement>('login-form').dispatchEvent(new Event('submit', { cancelable: true }));
    await vi.waitFor(() => expect($('login-error').hidden).toBe(false));
    expect(($('login-submit') as HTMLButtonElement).disabled).toBe(true);
    expect($('login-error').textContent).toContain('2');
    await vi.waitFor(() => expect(($('login-submit') as HTMLButtonElement).disabled).toBe(false), { timeout: 4000 });
    expect($('login-error').hidden).toBe(true);
  });

  it('successful login stores the token, closes, and restores focus', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(200, { token: 'jwt', token_type: 'Bearer', expires_in: 3600 })));
    await mount('LoginModal');
    $('opener').focus();
    openModal();
    $<HTMLInputElement>('login-username').value = 'u';
    $<HTMLInputElement>('login-password').value = 'p';
    $<HTMLFormElement>('login-form').dispatchEvent(new Event('submit', { cancelable: true }));
    await vi.waitFor(() => expect($('login-modal').hidden).toBe(true));
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe('jwt');
    expect(document.activeElement).toBe($('opener'));
  });
});

describe('Uploader / Sample Tomb', () => {
  const extra = '<div data-terminal-log></div>';

  it('guest: judge upload hidden, tomb disabled with a login prompt', async () => {
    await mount('Uploader', extra);
    expect($('up-guest').hidden).toBe(false);
    expect($('up-judge').hidden).toBe(true);
    expect($('up-tomb-guest').hidden).toBe(false);
    expect(($('up-tomb') as HTMLButtonElement).disabled).toBe(true);
  });

  it('judge: upload shown, tomb enabled; login/logout toggles the states', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'jwt');
    await mount('Uploader', extra);
    expect($('up-guest').hidden).toBe(true);
    expect($('up-judge').hidden).toBe(false);
    expect(($('up-tomb') as HTMLButtonElement).disabled).toBe(false);
    logout();
    expect($('up-guest').hidden).toBe(false);
    expect(($('up-tomb') as HTMLButtonElement).disabled).toBe(true);
  });

  it('judge: clicking the tomb shows a loading status and disables the button', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'jwt');
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {})));
    await mount('Uploader', extra);
    $('up-tomb').click();
    await tick();
    expect($('up-status').hidden).toBe(false);
    expect(($('up-tomb') as HTMLButtonElement).disabled).toBe(true);
  });

  it('judge: a failed tomb request shows an alert and re-enables the button', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'jwt');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(500, { error: { code: 'INTERNAL', message: 'm' } })));
    await mount('Uploader', extra);
    $('up-tomb').click();
    await vi.waitFor(() => expect($('up-error').hidden).toBe(false));
    expect(($('up-tomb') as HTMLButtonElement).disabled).toBe(false);
  });
});

describe('SemanticSearch', () => {
  it('guest sees the login prompt; judge sees the form', async () => {
    await mount('SemanticSearch');
    expect($('ss-guest').hidden).toBe(false);
    expect($('ss-form').hidden).toBe(true);
    sessionStorage.setItem(TOKEN_KEY, 'jwt');
    window.dispatchEvent(new CustomEvent('auth:changed'));
    expect($('ss-guest').hidden).toBe(true);
    expect($('ss-form').hidden).toBe(false);
    logout();
    expect($('ss-guest').hidden).toBe(false);
  });

  it('login button asks the modal to open with itself as opener', async () => {
    await mount('SemanticSearch');
    const seen = vi.fn();
    window.addEventListener('login:open', (e) => seen((e as CustomEvent).detail.opener));
    $('ss-login').click();
    expect(seen).toHaveBeenCalledWith($('ss-login'));
  });

  it('judge: empty query shows a validation error without calling the API', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'jwt');
    const f = vi.fn();
    vi.stubGlobal('fetch', f);
    await mount('SemanticSearch');
    $<HTMLFormElement>('ss-form').dispatchEvent(new Event('submit', { cancelable: true }));
    expect($('ss-error').hidden).toBe(false);
    expect(f).not.toHaveBeenCalled();
  });

  it('judge: renders results and the empty state', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'jwt');
    const hit = { summary: { id: 'r1', title: 'Title' }, similarity: 0.9 };
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(json(200, { results: [hit] }))
      .mockResolvedValueOnce(json(200, { results: [] })));
    await mount('SemanticSearch');
    $<HTMLTextAreaElement>('ss-q').value = 'plague';
    $<HTMLFormElement>('ss-form').dispatchEvent(new Event('submit', { cancelable: true }));
    await vi.waitFor(() => expect(document.querySelectorAll('#ss-results li').length).toBe(1));
    expect(document.querySelector('#ss-results a')?.textContent).toBe('Title');
    $<HTMLFormElement>('ss-form').dispatchEvent(new Event('submit', { cancelable: true }));
    await vi.waitFor(() => expect($('ss-status').hidden).toBe(false));
    await vi.waitFor(() => expect(document.querySelectorAll('#ss-results li').length).toBe(0));
  });

  it('judge: a 401 shows the expired state with a re-login button', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'jwt');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(401, { error: { code: 'UNAUTHORIZED', message: 'm' } })));
    await mount('SemanticSearch');
    $<HTMLTextAreaElement>('ss-q').value = 'plague';
    $<HTMLFormElement>('ss-form').dispatchEvent(new Event('submit', { cancelable: true }));
    await vi.waitFor(() => expect($('ss-error').hidden).toBe(false));
    expect($('ss-relogin').hidden).toBe(false);
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});
