import { describe, expect, it } from 'vitest';
import fc from 'fast-check';
import { countRecords, validateRecordCount, validateUpload, MAX_BATCH_RECORDS } from './upload';

/**
 * Feature: necromarc, Property 35: Upload file validation
 * **Validates: Requirements 13.9, 13.10, 13.11**
 */
describe('Property 35: Upload file validation', () => {
  const stem = fc.string({ maxLength: 20 });
  const ext = fc
    .constantFrom('.mrc', '.MRC', '.Mrc', '.mRc')
    .map((e) => e);
  const badSuffix = fc
    .constantFrom('.txt', '.mrc.bak', '.marc', '', '.mr', 'mrc', '.xml')
    .map((e) => e);

  it('accepts iff name ends in .mrc (case-insensitive) and size is within (0, max]', () => {
    fc.assert(
      fc.property(
        stem,
        fc.oneof(ext, badSuffix),
        fc.integer({ min: 0, max: 20_000 }),
        fc.integer({ min: 1, max: 10_000 }),
        (s, suffix, size, max) => {
          const name = s + suffix;
          const res = validateUpload({ name, size }, max);
          const expected = /\.mrc$/i.test(name) && size > 0 && size <= max;
          expect(res.ok).toBe(expected);
          if (!res.ok) expect(res.errorKey).toMatch(/^summon\.error\./);
        },
      ),
    );
  });

  it('rejects wrong extension with the extension error and oversize with the size error', () => {
    fc.assert(
      fc.property(stem, fc.integer({ min: 1, max: 1000 }), (s, max) => {
        const bad = validateUpload({ name: s + '.txt', size: 1 }, max);
        expect(bad).toEqual({ ok: false, errorKey: 'summon.error.extension' });
        const big = validateUpload({ name: s + '.mrc', size: max + 1 }, max);
        expect(big).toEqual({ ok: false, errorKey: 'summon.error.too_large' });
      }),
    );
  });

  it('record count validation accepts iff count <= 5, and countRecords counts 0x1D bytes', () => {
    fc.assert(
      fc.property(fc.uint8Array({ maxLength: 200 }), (bytes) => {
        const n = bytes.filter((b) => b === 0x1d).length;
        expect(countRecords(bytes)).toBe(n);
        expect(validateRecordCount(n).ok).toBe(n <= MAX_BATCH_RECORDS);
      }),
    );
  });
});
