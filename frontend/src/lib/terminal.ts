import type { Anomaly, DecayEntry, Field, RawRecord } from './api';
import { t } from '../i18n/i18n';

export interface TerminalLine {
  /** Display text, e.g. `=245 10$aTitle`. */
  text: string;
  tag: string;
  /** Synthetic red "missing" line for an absent 520 or 650. */
  missing?: boolean;
  ai?: boolean;
}

export type LineKind = 'normal' | 'success' | 'failure' | 'stage';

export function formatField(f: Field): string {
  if ('data' in f) return `=${f.tag}  ${f.data}`;
  const subs = f.subfields.map(([c, v]) => `$${c}${v}`).join('');
  return `=${f.tag} ${f.ind1 || '#'}${f.ind2 || '#'}${subs}`;
}

/** One line per field (LDR first when present). Absent 520/650 get a synthetic line in tag order. */
export function buildLines(raw: RawRecord): TerminalLine[] {
  const lines: TerminalLine[] = [];
  if (raw.leader != null) lines.push({ text: `=LDR  ${raw.leader}`, tag: 'LDR' });
  const fields = [...raw.fields];
  for (const tag of ['520', '650']) {
    if (fields.some((f) => f.tag === tag)) continue;
    const at = fields.findIndex((f) => f.tag > tag);
    const synth = { tag, data: 'missing', synthetic: true } as Field;
    fields.splice(at === -1 ? fields.length : at, 0, synth);
  }
  for (const f of fields) {
    const synthetic = (f as { synthetic?: boolean }).synthetic === true;
    lines.push(
      synthetic
        ? { text: `=${f.tag}  missing`, tag: f.tag, missing: true }
        : { text: formatField(f), tag: f.tag, ai: f.ai === true },
    );
  }
  return lines;
}

/** Pure mapping of display-line index to the decay rule names that mark it. */
export function markDecay(
  lines: TerminalLine[],
  breakdown: DecayEntry[],
  anomalies: Anomaly[] = [],
): Map<number, string[]> {
  const marks = new Map<number, string[]>();
  const add = (i: number, rule: string) => {
    if (i < 0) return;
    const cur = marks.get(i) ?? [];
    if (!cur.includes(rule)) cur.push(rule);
    marks.set(i, cur);
  };
  const idx = (tag: string) => lines.findIndex((l) => l.tag === tag);
  for (const { rule } of breakdown) {
    if (rule === 'missing_520') add(idx('520'), rule);
    else if (rule === 'missing_650') add(idx('650'), rule);
    else if (rule === 'invalid_year') add(idx('008'), rule);
    else if (rule === 'missing_100d') add(idx('100'), rule);
    else if (rule === 'anomaly') {
      add(idx('LDR'), rule);
      for (const a of anomalies) if (a.tag) add(idx(a.tag), rule);
    }
  }
  return marks;
}

/** Rule label key; unknown rules fall back to the rule name. */
export function ruleLabel(rule: string): string {
  const key = `terminal.rule.${rule}`;
  const s = t(key);
  return s === key ? rule : s;
}

function makeLi(doc: Document, text: string, kind: LineKind): HTMLLIElement {
  const li = doc.createElement('li');
  li.className = 'terminal-line';
  li.dataset.kind = kind;
  li.setAttribute('dir', 'ltr');
  li.setAttribute('lang', 'und');
  const span = doc.createElement('span');
  span.textContent = text;
  li.append(span);
  return li;
}

/** Append one log line (pipeline stage, success, failure). Announced via the list's live region. */
export function appendLine(list: HTMLElement, text: string, kind: LineKind = 'normal'): HTMLLIElement {
  const li = makeLi(list.ownerDocument, text, kind);
  if (kind === 'failure') li.classList.add('terminal-failure');
  if (kind === 'success') li.classList.add('terminal-success');
  list.append(li);
  return li;
}

export function showSuccess(list: HTMLElement, text = t('terminal.success')): HTMLLIElement {
  return appendLine(list, text, 'success');
}
export function showFailure(list: HTMLElement, text = t('terminal.failure')): HTMLLIElement {
  return appendLine(list, text, 'failure');
}

/** Replace list content with the raw record, marking decay lines with a red indicator and text label. */
export function renderRecord(list: HTMLElement, raw: RawRecord, breakdown: DecayEntry[] = []): void {
  const doc = list.ownerDocument;
  const lines = buildLines(raw);
  const marks = markDecay(lines, breakdown, raw.anomalies ?? []);
  list.replaceChildren();
  lines.forEach((line, i) => {
    const li = makeLi(doc, line.text, 'normal');
    const rules = marks.get(i);
    if (line.missing || rules) li.classList.add('terminal-decay');
    if (rules) {
      const mark = doc.createElement('span');
      mark.className = 'terminal-decay-label';
      mark.textContent = ` ⚠ ${rules.map(ruleLabel).join(', ')}`;
      li.append(mark);
    }
    if (line.ai) {
      const ai = doc.createElement('span');
      ai.className = 'terminal-ai';
      ai.textContent = ` ${t('terminal.ai')}`;
      li.classList.add('terminal-ai-line');
      li.append(ai);
    }
    list.append(li);
  });
}
