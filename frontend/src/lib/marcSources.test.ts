import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { MARC_SOURCES } from './marcSources';
import en from '../i18n/en.json';
import ar from '../i18n/ar.json';

describe('MARC sources', () => {
  it('has exactly three unique https URLs', () => {
    expect(MARC_SOURCES).toHaveLength(3);
    const urls = MARC_SOURCES.map((s) => s.url);
    expect(new Set(urls).size).toBe(3);
    urls.forEach((u) => expect(new URL(u).protocol).toBe('https:'));
  });

  it('has every i18n key in both dictionaries', () => {
    const keys = [
      ...MARC_SOURCES.flatMap((s) => [s.nameKey, s.noteKey]),
      'sources.title',
      'sources.intro',
      'sources.tip',
    ];
    for (const k of keys) {
      expect(en as Record<string, string>).toHaveProperty([k]);
      expect(ar as Record<string, string>).toHaveProperty([k]);
    }
  });

  it('renders links with target and rel in the component template', () => {
    const src = readFileSync(resolve(process.cwd(), 'src/components/MarcSources.astro'), 'utf-8');
    expect(src).toContain('target="_blank"');
    expect(src).toContain('rel="noopener noreferrer"');
    expect(src).toContain('href={s.url}');
  });
});
