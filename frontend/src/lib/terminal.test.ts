import { describe, it, expect } from 'vitest';
import { buildLines, markDecay, formatField } from './terminal';
import type { RawRecord } from './api';

const raw: RawRecord = {
  leader: '00000nam a2200000 a 4500',
  fields: [
    { tag: '008', data: '700101s0000' },
    { tag: '100', subfields: [['a', 'X']] },
    { tag: '245', ind1: '1', ind2: '0', subfields: [['a', 'Title'], ['b', 'Sub']] },
    { tag: '700', subfields: [['a', 'Y']], ai: true },
  ],
};

describe('terminal', () => {
  it('formats fields', () => {
    expect(formatField(raw.fields[2])).toBe('=245 10$aTitle$bSub');
    expect(formatField(raw.fields[0])).toBe('=008  700101s0000');
  });
  it('inserts missing 520/650 in tag order', () => {
    const tags = buildLines(raw).map((l) => l.tag);
    expect(tags).toEqual(['LDR', '008', '100', '245', '520', '650', '700']);
    expect(buildLines(raw).filter((l) => l.missing).map((l) => l.text)).toEqual(['=520  missing', '=650  missing']);
  });
  it('marks lines by rule', () => {
    const lines = buildLines(raw);
    const m = markDecay(lines, [
      { rule: 'missing_520', points: 30 },
      { rule: 'invalid_year', points: 20 },
      { rule: 'missing_100d', points: 15 },
      { rule: 'anomaly', points: 10 },
    ], [{ kind: 'structural', code: 'x', message: 'm', tag: '245' }]);
    expect(m.get(1)).toEqual(['invalid_year']);
    expect(m.get(2)).toEqual(['missing_100d']);
    expect(m.get(3)).toEqual(['anomaly']);
    expect(m.get(4)).toEqual(['missing_520']);
    expect(m.get(0)).toEqual(['anomaly']);
    expect(m.has(5)).toBe(false);
  });
  it('flags AI lines', () => {
    expect(buildLines(raw).find((l) => l.tag === '700')?.ai).toBe(true);
  });
});
