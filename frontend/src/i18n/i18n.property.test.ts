import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import en from './en.json';
import ar from './ar.json';
import {
  DICTS, STORAGE_KEY, resolveLang, translate, dirFor, setLang, initI18n, getLang, type Dict, type Lang,
} from './i18n';

// Seeded PRNG so randomised cases are reproducible.
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}
const ALPHABET = 'abcXYZ019._-: {}\u0627\u0628\u062a';
function randStr(r: () => number, max = 12): string {
  let o = '';
  for (let i = Math.floor(r() * (max + 1)); i > 0; i--) o += ALPHABET[Math.floor(r() * ALPHABET.length)];
  return o;
}

const srcDir = fileURLToPath(new URL('..', import.meta.url));
const frontendDir = fileURLToPath(new URL('../..', import.meta.url));

describe('Property 33: i18n key parity and fallback', () => {
  /** Validates: Requirements 14.9, 14.10, 14.11 */
  it('en and ar have an empty symmetric key difference', () => {
    const e = new Set(Object.keys(en));
    const a = new Set(Object.keys(ar));
    expect([...e].filter((k) => !a.has(k))).toEqual([]);
    expect([...a].filter((k) => !e.has(k))).toEqual([]);
  });

  it('every translation value is a non-empty string', () => {
    for (const d of [en, ar] as Dict[]) {
      for (const [k, v] of Object.entries(d)) {
        expect(typeof v, k).toBe('string');
        expect(v.trim().length, k).toBeGreaterThan(0);
      }
    }
  });

  it('{placeholders} match between en and ar for each key', () => {
    const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();
    for (const k of Object.keys(en)) {
      expect(ph((ar as Dict)[k]), k).toEqual(ph((en as Dict)[k]));
    }
  });

  it('translate: selected language, else English, else key (random dictionaries)', () => {
    const r = rng(33);
    for (let i = 0; i < 500; i++) {
      const keys = Array.from({ length: 6 }, () => randStr(r, 6)).filter((k) => !/[{}]/.test(k));
      const dicts: Record<Lang, Dict> = { en: {}, ar: {} };
      for (const k of keys) {
        if (r() < 0.6) dicts.en[k] = 'E:' + randStr(r);
        if (r() < 0.6) dicts.ar[k] = 'A:' + randStr(r);
      }
      const probe = [...keys, randStr(r, 8), 'constructor', 'toString', '__proto__'];
      for (const lang of ['en', 'ar'] as Lang[]) {
        for (const k of probe) {
          const own = (d: Dict) => Object.prototype.hasOwnProperty.call(d, k);
          const expected = own(dicts[lang]) ? dicts[lang][k] : own(dicts.en) ? dicts.en[k] : k;
          expect(translate(k, lang, undefined, dicts)).toBe(expected);
        }
      }
    }
  });

  it('translate on real dictionaries returns the selected-language string for every key', () => {
    for (const lang of ['en', 'ar'] as Lang[]) {
      for (const k of Object.keys(en)) expect(translate(k, lang)).toBe(DICTS[lang][k]);
    }
  });

  it('resolveLang returns en for everything except exactly "en" or "ar"', () => {
    const r = rng(7);
    expect(resolveLang('en')).toBe('en');
    expect(resolveLang('ar')).toBe('ar');
    const fixed: unknown[] = [null, undefined, '', 0, 1, true, {}, [], ' ar', 'ar ', 'AR', 'En', 'ar-SA', 'fr'];
    for (const v of fixed) expect(resolveLang(v)).toBe('en');
    for (let i = 0; i < 500; i++) {
      const s = randStr(r);
      expect(resolveLang(s)).toBe(s === 'ar' ? 'ar' : 'en');
    }
  });
});

describe('language persistence and dir switching', () => {
  const store = new Map<string, string>();
  const g = globalThis as Record<string, unknown>;
  const root = { lang: '', dir: '', querySelectorAll: () => [] as unknown[] };
  const events: string[] = [];
  const saved = { ls: g.localStorage, doc: g.document, ce: g.CustomEvent };

  beforeEach(() => {
    store.clear();
    events.length = 0;
    root.lang = '';
    root.dir = '';
    g.localStorage = {
      getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
      setItem: (k: string, v: string) => void store.set(k, v),
    };
    g.CustomEvent = class { constructor(public type: string, public init?: unknown) {} };
    g.document = {
      documentElement: root,
      querySelectorAll: () => [],
      dispatchEvent: (e: { type: string }) => void events.push(e.type),
    };
  });
  afterEach(() => {
    g.localStorage = saved.ls;
    g.document = saved.doc;
    g.CustomEvent = saved.ce;
    setLang('en', false);
  });

  it('dirFor is rtl only for ar', () => {
    expect(dirFor('ar')).toBe('rtl');
    expect(dirFor('en')).toBe('ltr');
  });

  it('setLang updates html lang/dir, persists, and emits i18n:changed', () => {
    expect(setLang('ar')).toBe('ar');
    expect(root.lang).toBe('ar');
    expect(root.dir).toBe('rtl');
    expect(store.get(STORAGE_KEY)).toBe('ar');
    expect(events).toContain('i18n:changed');
    setLang('en');
    expect(root.dir).toBe('ltr');
    expect(store.get(STORAGE_KEY)).toBe('en');
  });

  it('invalid language falls back to en and persists en', () => {
    setLang('fr');
    expect(getLang()).toBe('en');
    expect(root.dir).toBe('ltr');
    expect(store.get(STORAGE_KEY)).toBe('en');
  });

  it('initI18n restores the stored language without rewriting storage', () => {
    store.set(STORAGE_KEY, 'ar');
    expect(initI18n()).toBe('ar');
    expect(root.dir).toBe('rtl');
    store.set(STORAGE_KEY, 'garbage');
    expect(initI18n()).toBe('en');
    expect(store.get(STORAGE_KEY)).toBe('garbage');
  });

  it('initI18n defaults to en when storage is empty or throws', () => {
    expect(initI18n()).toBe('en');
    g.localStorage = { getItem: () => { throw new Error('denied'); }, setItem: () => { throw new Error('denied'); } };
    expect(initI18n()).toBe('en');
    expect(() => setLang('ar')).not.toThrow();
    expect(getLang()).toBe('ar');
  });
});

describe('scripts/check-i18n.mjs', () => {
  it('exits 0 on the current dictionaries', () => {
    const res = spawnSync(process.execPath, ['scripts/check-i18n.mjs'], { cwd: frontendDir, encoding: 'utf8' });
    expect(res.status, res.stderr).toBe(0);
    expect(res.stdout).toMatch(/i18n OK/);
  });
});

function walk(dir: string, out: string[] = []): string[] {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
}

describe('RTL lint: no physical Tailwind direction utilities in src/', () => {
  // Matches (optionally variant-prefixed, optionally negative) physical utilities.
  const physical = /(?<![\w-])-?(?:ml|mr|pl|pr|left|right)-(?:[\w./[\]%()-]+)|(?<![\w-])text-(?:left|right)(?![\w-])/g;
  const files = walk(srcDir).filter((f) => /\.(astro|ts|tsx|js|jsx|html|css)$/.test(f) && !/\.test\.ts$/.test(f));

  it('scans at least one file', () => {
    expect(files.length).toBeGreaterThan(0);
  });

  it('detector flags physical utilities and ignores logical ones', () => {
    const flag = (s: string) => (s.match(physical) ?? []).length > 0;
    for (const bad of ['ml-4', 'mr-2', 'pl-3', 'pr-1', 'left-0', 'right-2', 'text-left', 'text-right', 'md:-ml-2', 'sm:pl-[3px]']) {
      expect(flag(`class="${bad}"`), bad).toBe(true);
    }
    for (const ok of ['ms-4', 'me-2', 'ps-3', 'pe-1', 'start-0', 'end-2', 'text-start', 'text-end', 'mt-2', 'bg-left-top-x', 'text-leftover']) {
      expect(flag(`class="${ok}"`), ok).toBe(false);
    }
  });

  it('no file uses ml-/mr-/pl-/pr-/left-/right-/text-left/text-right', () => {
    const violations: string[] = [];
    for (const f of files) {
      readFileSync(f, 'utf8').split('\n').forEach((line, i) => {
        const m = line.match(physical);
        if (m) violations.push(`${relative(srcDir, f)}:${i + 1} ${m.join(' ')}`);
      });
    }
    expect(violations).toEqual([]);
  });
});

describe('MARC and terminal elements stay LTR', () => {
  const css = readFileSync(join(srcDir, 'styles/global.css'), 'utf8');

  it('global.css forces direction: ltr with bidi isolation on .marc-text and .terminal', () => {
    const m = css.match(/\.marc-text\s*,\s*\.terminal\s*\{([^}]*)\}/);
    expect(m, 'combined .marc-text/.terminal rule').not.toBeNull();
    expect(m![1]).toMatch(/direction:\s*ltr/);
    expect(m![1]).toMatch(/unicode-bidi:\s*isolate/);
  });

  it('no stylesheet overrides .marc-text/.terminal to rtl', () => {
    for (const f of walk(srcDir).filter((p) => /\.(css|astro)$/.test(p))) {
      const text = readFileSync(f, 'utf8');
      for (const rule of text.matchAll(/([^{}]*\b(?:marc-text|terminal)\b[^{}]*)\{([^}]*)\}/g)) {
        expect(rule[2], `${f}: ${rule[1].trim()}`).not.toMatch(/direction:\s*rtl/);
      }
    }
  });

  it('no markup element with marc-text/terminal class sets dir="rtl" or dir="auto"', () => {
    for (const f of walk(srcDir).filter((p) => /\.(astro|html|ts)$/.test(p) && !/\.test\.ts$/.test(p))) {
      const text = readFileSync(f, 'utf8');
      for (const tag of text.matchAll(/<[a-z][^>]*>/gi)) {
        if (/\b(marc-text|terminal)\b/.test(tag[0])) {
          expect(tag[0], f).not.toMatch(/\bdir=["']?(rtl|auto)/);
        }
      }
    }
  });
});
