import en from './en.json';
import ar from './ar.json';

export type Lang = 'en' | 'ar';
export type Dict = Record<string, string>;

export const STORAGE_KEY = 'necromarc.lang';
export const DICTS: Record<Lang, Dict> = { en, ar };

/** Accepts only the exact strings "en" or "ar"; anything else yields "en". */
export function resolveLang(stored: unknown): Lang {
  return stored === 'en' || stored === 'ar' ? stored : 'en';
}

export function dirFor(lang: Lang): 'ltr' | 'rtl' {
  return lang === 'ar' ? 'rtl' : 'ltr';
}

/** Lookup in `dicts[lang]`, then `dicts.en`, then the key itself. */
export function translate(
  key: string,
  lang: Lang,
  params?: Record<string, string | number>,
  dicts: Record<Lang, Dict> = DICTS,
): string {
  const own = Object.prototype.hasOwnProperty;
  let s: string;
  if (own.call(dicts[lang], key)) s = dicts[lang][key];
  else if (own.call(dicts.en, key)) s = dicts.en[key];
  else s = key;
  if (params) {
    s = s.replace(/\{(\w+)\}/g, (m, k: string) =>
      own.call(params, k) ? String(params[k]) : m,
    );
  }
  return s;
}

/** True when `key` has a translation (English is the fallback, so it holds every key). */
export function hasKey(key: string, dicts: Record<Lang, Dict> = DICTS): boolean {
  return Object.prototype.hasOwnProperty.call(dicts.en, key);
}

let current: Lang = 'en';

export function getLang(): Lang {
  return current;
}

export function t(key: string, params?: Record<string, string | number>): string {
  return translate(key, current, params);
}

function readStored(): unknown {
  try {
    return globalThis.localStorage?.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/** Re-render all [data-i18n] (text) and [data-i18n-attr] ("attr:key") nodes. */
export function renderAll(root: ParentNode = document): void {
  root.querySelectorAll<HTMLElement>('[data-i18n]').forEach((el) => {
    el.textContent = t(el.dataset.i18n as string);
  });
  root.querySelectorAll<HTMLElement>('[data-i18n-attr]').forEach((el) => {
    const [attr, key] = (el.dataset.i18nAttr as string).split(':');
    if (attr && key) el.setAttribute(attr, t(key));
  });
}

function applyToDocument(lang: Lang): void {
  const root = document.documentElement;
  root.lang = lang;
  root.dir = dirFor(lang);
  renderAll();
  document.dispatchEvent(new CustomEvent('i18n:changed', { detail: { lang } }));
}

export function setLang(lang: unknown, persist = true): Lang {
  current = resolveLang(lang);
  if (typeof document !== 'undefined') applyToDocument(current);
  if (persist) {
    try {
      globalThis.localStorage?.setItem(STORAGE_KEY, current);
    } catch {
      /* storage unavailable */
    }
  }
  return current;
}

/** Apply the stored language (or English) on page load. */
export function initI18n(): Lang {
  return setLang(readStored(), false);
}
