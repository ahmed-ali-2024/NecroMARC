import { describe, expect, it } from 'vitest';
import { ApiError } from './api';
import {
  DEFAULT_MAX_UPLOAD_BYTES,
  summonErrorView,
  validateUpload,
} from './upload';

describe('validateUpload', () => {
  it('accepts .mrc case-insensitively within the cap', () => {
    expect(validateUpload({ name: 'a.mrc', size: 1 }).ok).toBe(true);
    expect(validateUpload({ name: 'A.MRC', size: DEFAULT_MAX_UPLOAD_BYTES }).ok).toBe(true);
  });
  it('rejects wrong extension, empty, and oversize', () => {
    expect(validateUpload({ name: 'a.txt', size: 5 })).toEqual({ ok: false, errorKey: 'summon.error.extension' });
    expect(validateUpload({ name: 'a.mrc.txt', size: 5 }).ok).toBe(false);
    expect(validateUpload({ name: 'a.mrc', size: 0 })).toEqual({ ok: false, errorKey: 'summon.error.empty' });
    expect(validateUpload({ name: 'a.mrc', size: DEFAULT_MAX_UPLOAD_BYTES + 1 })).toEqual({
      ok: false,
      errorKey: 'summon.error.too_large',
    });
  });
});

describe('summonErrorView', () => {
  it('maps statuses', () => {
    expect(summonErrorView(new ApiError(401, 'X', 'm')).expired).toBe(true);
    expect(summonErrorView(new ApiError(413, 'X', 'm')).key).toBe('summon.error.payload_too_large');
    expect(summonErrorView(new ApiError(422, 'X', 'm')).key).toBe('summon.error.unparseable');
    expect(summonErrorView(new ApiError(429, 'X', 'm', 7))).toMatchObject({ params: { seconds: 7 } });
    expect(summonErrorView(new ApiError(429, 'X', 'm')).key).toBe('summon.error.rate_limited_unknown');
    expect(summonErrorView(new Error('x')).key).toBe('error.unknown');
  });
});
