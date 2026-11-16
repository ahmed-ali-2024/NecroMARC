import { describe, it, expect } from 'vitest';
import en from './en.json';
import ar from './ar.json';
import { resolveLang, translate, dirFor } from './i18n';

describe('i18n', () => {
  it('has identical key sets', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(ar).sort());
  });
  it('resolveLang accepts only en/ar', () => {
    expect(resolveLang('ar')).toBe('ar');
    expect(resolveLang('en')).toBe('en');
    for (const v of [null, undefined, 'AR', 'fr', '', 1]) expect(resolveLang(v)).toBe('en');
  });
  it('falls back to English then key', () => {
    const d = { en: { a: 'A', b: 'B' }, ar: { a: 'ا' } };
    expect(translate('a', 'ar', undefined, d)).toBe('ا');
    expect(translate('b', 'ar', undefined, d)).toBe('B');
    expect(translate('zzz', 'ar', undefined, d)).toBe('zzz');
    expect(translate('toString', 'en', undefined, d)).toBe('toString');
  });
  it('maps dir', () => {
    expect(dirFor('ar')).toBe('rtl');
    expect(dirFor('en')).toBe('ltr');
  });
});
