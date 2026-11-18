import { existsSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import en from '../../i18n/en.json';
import ar from '../../i18n/ar.json';

const page = readFileSync(new URL('./index.astro', import.meta.url), 'utf8');
const header = readFileSync(new URL('../../components/Header.astro', import.meta.url), 'utf8');
const aboutKeys = (d: Record<string, string>) => Object.keys(d).filter((k) => k.startsWith('about.'));

describe('about page', () => {
  it('has a single h1 and h2 sections', () => {
    expect(page.match(/<h1\b/g)).toHaveLength(1);
    expect(page.match(/<h2\b/g)!.length).toBeGreaterThanOrEqual(5);
  });
  it('links to GitHub safely', () => {
    expect(page).toContain('https://github.com/ahmed-ali-2024/NecroMARC');
    expect(page).toMatch(/target="_blank" rel="noopener noreferrer"/);
  });
  it('keeps MARC snippets LTR', () => {
    expect(page).toMatch(/class="marc-text" dir="ltr"[^>]*>\$9 NecroMARC-AI/);
  });
  it('uses logical utilities only', () => {
    expect(page).not.toMatch(/\b(?:ml|mr|pl|pr|left|right|text-left|text-right)-/);
    expect(header).not.toMatch(/\b(?:ml|mr|pl|pr|text-left|text-right)-/);
  });
  it('uses BASE_URL for internal links', () => {
    expect(page).toContain('import.meta.env.BASE_URL');
    expect(page).not.toMatch(/href="\/[^"]*"/);
  });
  it('every data-i18n key exists in both dictionaries', () => {
    const keys = [...page.matchAll(/data-i18n="([^"]+)"/g)].map((m) => m[1]);
    for (const k of keys) {
      expect(en, k).toHaveProperty([k]);
      expect(ar, k).toHaveProperty([k]);
    }
  });
});

describe('about nav and dictionaries', () => {
  it('Header links to the About page with nav.about', () => {
    expect(header).toContain('href={`${base}/about/`}');
    expect(header).toContain('data-i18n="nav.about"');
  });
  it('about.* keys are in parity and non-empty', () => {
    expect(aboutKeys(en).sort()).toEqual(aboutKeys(ar).sort());
    for (const k of aboutKeys(en)) {
      expect((en as Record<string, string>)[k].trim()).not.toBe('');
      expect((ar as Record<string, string>)[k].trim()).not.toBe('');
    }
  });
  it('never calls MARC 21 dead', () => {
    for (const d of [en, ar] as Record<string, string>[]) {
      for (const k of aboutKeys(d)) expect(d[k]).not.toMatch(/\bdead\b|ميت/i);
    }
  });
  it('states MARC 21 is actively maintained', () => {
    expect(en['about.what.p2']).toMatch(/actively maintained/);
  });
  it('builds into dist when a build exists', () => {
    const out = new URL('../../../dist/about/index.html', import.meta.url);
    if (existsSync(out)) expect(readFileSync(out, 'utf8')).toContain('NecroMARC');
  });
});
