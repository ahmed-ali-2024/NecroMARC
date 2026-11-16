import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { ApiError } from './api';
import {
  validateSemanticQuery,
  semanticErrorView,
  formatSimilarity,
  chamberHref,
  MAX_SEMANTIC_QUERY,
} from './semantic';

describe('validateSemanticQuery', () => {
  it('rejects empty and whitespace-only', () => {
    expect(validateSemanticQuery('')).toEqual({ ok: false, errorKey: 'semantic.error.empty' });
    expect(validateSemanticQuery('   ')).toEqual({ ok: false, errorKey: 'semantic.error.empty' });
  });
  it('accepts 1 and 1000 chars, rejects 1001', () => {
    expect(validateSemanticQuery('a').ok).toBe(true);
    expect(validateSemanticQuery('a'.repeat(MAX_SEMANTIC_QUERY)).ok).toBe(true);
    expect(validateSemanticQuery('a'.repeat(MAX_SEMANTIC_QUERY + 1))).toEqual({
      ok: false,
      errorKey: 'semantic.error.too_long',
    });
  });
  it('property: valid iff trimmed length in 1..1000', () => {
    fc.assert(
      fc.property(fc.string({ maxLength: 1100 }), (s) => {
        const n = Array.from(s.trim()).length;
        expect(validateSemanticQuery(s).ok).toBe(n >= 1 && n <= 1000);
      }),
    );
  });
});

describe('semanticErrorView', () => {
  it('maps statuses', () => {
    expect(semanticErrorView(new ApiError(401, 'UNAUTHENTICATED', 'x'))).toMatchObject({ expired: true });
    expect(semanticErrorView(new ApiError(429, 'RATE_LIMITED', 'x', 7))).toEqual({
      key: 'semantic.error.rate_limited',
      params: { seconds: 7 },
      expired: false,
    });
    expect(semanticErrorView(new ApiError(429, 'RATE_LIMITED', 'x')).key).toBe('semantic.error.rate_limited_unknown');
    expect(semanticErrorView(new ApiError(502, 'X', 'x')).key).toBe('semantic.error.upstream');
    expect(semanticErrorView(new Error('x')).key).toBe('error.unknown');
  });
});

describe('formatters', () => {
  it('formats similarity', () => {
    expect(formatSimilarity(0.8734)).toBe('87%');
    expect(formatSimilarity(2)).toBe('100%');
  });
  it('builds chamber href with base prefix', () => {
    expect(chamberHref('/app/', 'a b')).toBe('/app/chamber/?id=a%20b');
    expect(chamberHref('/', 'x')).toBe('/chamber/?id=x');
  });
});
