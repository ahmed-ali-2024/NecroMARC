import { ApiError, exportRecord, exportUrl, errorKey } from './api';
import type { DecayEntry, ExportFormat, RawRecord, RecordDetail, ResurrectResponse } from './api';
import { t } from '../i18n/i18n';
import { ruleLabel } from './terminal';

export const EXPORT_FORMATS: ExportFormat[] = ['mrc', 'marcxml', 'jsonld'];

export interface CardModel {
  id: string;
  summary: string;
  subjects: string[];
  language: string;
  year: number | null;
  decayScore: number;
  breakdown: DecayEntry[];
  /** Vitality of the raw record (100 - decay). */
  vitalityBefore: number;
  vitalityAfter: number;
  /** Tags of healed fields written by the AI. */
  aiTags: string[];
}

const clamp = (n: number) => Math.max(0, Math.min(100, Math.round(n)));

/** Tags (deduplicated, in order) of healed fields flagged `ai: true`. */
export function aiTags(healed: RawRecord | null): string[] {
  const out: string[] = [];
  for (const f of healed?.fields ?? []) if (f.ai === true && !out.includes(f.tag)) out.push(f.tag);
  return out;
}

/** Pure view model for a resurrected record; null when it has no resurrection data. */
export function buildCardModel(d: RecordDetail): CardModel | null {
  if (!d.resurrection) return null;
  return {
    id: d.id,
    summary: d.resurrection.healed_summary,
    subjects: d.resurrection.inferred_subjects,
    language: d.resurrection.language_name,
    year: d.resurrection.normalized_year,
    decayScore: clamp(d.decay.score),
    breakdown: d.decay.breakdown,
    vitalityBefore: clamp(100 - d.decay.score),
    vitalityAfter: clamp(d.vitality_score ?? 0),
    aiTags: aiTags(d.healed),
  };
}

/** i18n key for an export failure: 404 and 422 have dedicated messages. */
export function exportErrorKey(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 404) return 'card.export.error.404';
    if (e.status === 422) return 'card.export.error.422';
    return errorKey(e.code);
  }
  return 'error.unknown';
}

const FORMAT_KEY: Record<ExportFormat, string> = {
  mrc: 'card.export.mrc',
  marcxml: 'card.export.marcxml',
  jsonld: 'card.export.jsonld',
};

function el<K extends keyof HTMLElementTagNameMap>(
  doc: Document,
  tag: K,
  cls?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const e = doc.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** Decay_Score plus a list of rule name and points. */
export function renderDecayBreakdown(doc: Document, score: number, breakdown: DecayEntry[]): HTMLElement {
  const wrap = el(doc, 'section', 'card-decay');
  wrap.append(el(doc, 'h3', 'card-heading', t('card.decay.title')));
  wrap.append(el(doc, 'p', 'card-decay-score', t('card.decay.score', { score })));
  const ul = el(doc, 'ul', 'card-decay-list');
  for (const b of breakdown) {
    ul.append(el(doc, 'li', 'card-decay-item', t('card.decay.item', { name: ruleLabel(b.rule), points: b.points })));
  }
  wrap.append(ul);
  return wrap;
}

function renderMeter(doc: Document, label: string, value: number): HTMLElement {
  const row = el(doc, 'div', 'card-meter');
  const meter = el(doc, 'div', 'card-meter-track');
  meter.setAttribute('role', 'meter');
  meter.setAttribute('aria-valuemin', '0');
  meter.setAttribute('aria-valuemax', '100');
  meter.setAttribute('aria-valuenow', String(value));
  meter.setAttribute('aria-label', label);
  const fill = el(doc, 'div', 'card-meter-fill');
  fill.style.inlineSize = `${value}%`;
  meter.append(fill);
  row.append(el(doc, 'span', 'card-meter-label', `${label}: ${value}`), meter);
  return row;
}

export interface ExportControls {
  root: HTMLElement;
  setDisabled(disabled: boolean): void;
  error: HTMLElement;
}

/** Three export links. A click downloads through exportRecord so 404/422 can be shown. */
export function renderExportButtons(doc: Document, id: string, disabled = false): ExportControls {
  const root = el(doc, 'div', 'card-export');
  const buttons = el(doc, 'div', 'card-export-buttons');
  const error = el(doc, 'p', 'card-export-error');
  error.setAttribute('role', 'alert');
  error.hidden = true;
  const links: HTMLAnchorElement[] = [];
  const setDisabled = (v: boolean) => {
    for (const a of links) {
      a.setAttribute('aria-disabled', String(v));
      a.tabIndex = v ? -1 : 0;
    }
    root.setAttribute('aria-busy', String(v));
  };
  for (const fmt of EXPORT_FORMATS) {
    const a = el(doc, 'a', 'card-export-link', t(FORMAT_KEY[fmt]));
    a.href = exportUrl(id, fmt);
    a.dataset.format = fmt;
    a.addEventListener('click', async (ev) => {
      ev.preventDefault();
      if (a.getAttribute('aria-disabled') === 'true') return;
      error.hidden = true;
      try {
        const { blob, filename } = await exportRecord(id, fmt);
        const url = URL.createObjectURL(blob);
        const dl = el(doc, 'a');
        dl.href = url;
        dl.download = filename ?? `${id}.${fmt}`;
        doc.body.append(dl);
        dl.click();
        dl.remove();
        URL.revokeObjectURL(url);
      } catch (e) {
        error.textContent = t(exportErrorKey(e));
        error.hidden = false;
      }
    });
    links.push(a);
    buttons.append(a);
  }
  root.append(buttons, error);
  setDisabled(disabled);
  return { root, setDisabled, error };
}

/** Replace `host` content with the resurrected card. */
export function renderCard(host: HTMLElement, m: CardModel): ExportControls {
  const doc = host.ownerDocument;
  host.replaceChildren();
  host.removeAttribute('aria-busy');
  host.append(el(doc, 'h2', 'card-title', t('card.title')));
  const p = el(doc, 'p', 'card-summary', m.summary);
  if (m.aiTags.length) {
    p.append(el(doc, 'span', 'card-ai', ` ${t('card.ai')}`));
  }
  host.append(p);
  const meta = el(doc, 'p', 'card-meta');
  meta.append(
    el(doc, 'span', '', t('card.language', { language: m.language })),
    doc.createTextNode(' · '),
    el(doc, 'span', '', t('card.year', { year: m.year ?? t('card.year.unknown') })),
  );
  host.append(meta);
  const subj = el(doc, 'ul', 'card-subjects');
  subj.setAttribute('aria-label', t('card.subjects'));
  for (const s of m.subjects) {
    const li = el(doc, 'li', 'card-badge', s);
    subj.append(li);
  }
  if (m.aiTags.length) subj.append(el(doc, 'li', 'card-ai', t('card.ai')));
  host.append(subj);
  host.append(el(doc, 'h3', 'card-heading', t('chamber.vitality')));
  host.append(renderMeter(doc, t('card.vitality.before'), m.vitalityBefore));
  host.append(renderMeter(doc, t('card.vitality.after'), m.vitalityAfter));
  if (m.aiTags.length) {
    host.append(el(doc, 'p', 'card-ai-fields', t('card.ai.fields', { tags: m.aiTags.join(', ') })));
  }
  host.append(renderDecayBreakdown(doc, m.decayScore, m.breakdown));
  const exp = renderExportButtons(doc, m.id);
  host.append(exp.root);
  return exp;
}

export interface ResurrectionHandlers {
  onSuccess(detail: RecordDetail): void;
  onFailure?(error: unknown): void;
}

/**
 * Pending state: progress shown synchronously, aria-busy, exports disabled.
 * Failure: localized error plus a retry that re-sends the same payload.
 * The caller keeps the raw record visible in the Terminal_Panel.
 */
export function runResurrection(
  host: HTMLElement,
  records: RawRecord[],
  send: (records: RawRecord[], signal: AbortSignal) => Promise<ResurrectResponse>,
  handlers: ResurrectionHandlers,
  timeoutMs: number,
): AbortController {
  const doc = host.ownerDocument;
  const controller = new AbortController();
  host.replaceChildren();
  host.setAttribute('aria-busy', 'true');
  const progress = el(doc, 'p', 'card-progress', t('card.pending'));
  progress.setAttribute('role', 'status');
  host.append(progress);
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const fail = (e: unknown) => {
    host.removeAttribute('aria-busy');
    host.replaceChildren();
    const msg = el(doc, 'p', 'card-error', t('card.error'));
    msg.setAttribute('role', 'alert');
    const retry = el(doc, 'button', 'card-retry', t('common.retry'));
    retry.type = 'button';
    retry.addEventListener('click', () => runResurrection(host, records, send, handlers, timeoutMs));
    host.append(msg, retry);
    handlers.onFailure?.(e);
  };
  send(records, controller.signal)
    .then((res) => {
      const r = res.results[0];
      if (r && r.status === 'success') {
        host.removeAttribute('aria-busy');
        handlers.onSuccess(r.record);
      } else {
        fail(r && r.status === 'failure' ? r.error : new Error('empty'));
      }
    })
    .catch(fail)
    .finally(() => clearTimeout(timer));
  return controller;
}
