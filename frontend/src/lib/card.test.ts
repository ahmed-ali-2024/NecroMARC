import { describe, it, expect } from 'vitest';
import { buildCardModel, exportErrorKey, aiTags } from './card';
import { ApiError } from './api';
import type { RecordDetail } from './api';

const detail = {
  id: 'abc',
  decay: { score: 65, breakdown: [{ rule: 'missing_520', points: 30 }] },
  vitality_score: 85,
  healed: { leader: null, fields: [{ tag: '520', data: 'x', ai: true }, { tag: '520', data: 'y', ai: true }, { tag: '245', data: 'z' }] },
  resurrection: { healed_summary: 'S', inferred_subjects: ['a'], normalized_year: 1900, language_name: 'Arabic', json_ld: {} },
} as unknown as RecordDetail;

describe('card', () => {
  it('builds before/after vitality and AI tags', () => {
    const m = buildCardModel(detail)!;
    expect(m.vitalityBefore).toBe(35);
    expect(m.vitalityAfter).toBe(85);
    expect(m.aiTags).toEqual(['520']);
    expect(m.language).toBe('Arabic');
  });
  it('returns null without resurrection', () => {
    expect(buildCardModel({ ...detail, resurrection: null })).toBeNull();
    expect(aiTags(null)).toEqual([]);
  });
  it('maps export errors', () => {
    expect(exportErrorKey(new ApiError(404, 'NOT_FOUND', 'm'))).toBe('card.export.error.404');
    expect(exportErrorKey(new ApiError(422, 'X', 'm'))).toBe('card.export.error.422');
    expect(exportErrorKey(new ApiError(500, 'INTERNAL_ERROR', 'm'))).toBe('error.INTERNAL_ERROR');
    expect(exportErrorKey(new Error('x'))).toBe('error.unknown');
  });
});
