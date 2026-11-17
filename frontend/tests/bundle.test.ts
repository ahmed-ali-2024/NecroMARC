import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
// @ts-expect-error plain .mjs script without types
import { RULES, scanDir } from '../scripts/check-bundle.mjs';

describe('bundle secret gate', () => {
  it('flags each secret pattern by rule name only', () => {
    const dir = mkdtempSync(join(tmpdir(), 'bundle-'));
    mkdirSync(join(dir, 'a'));
    const samples = ['sk-or' + '-', 'AI' + 'za', 'ey' + 'JhbGciOiJI', 'service_role', 'SUPABASE_SERVICE_ROLE_KEY',
      'abc.supabase.co', 'JUDGE_PASSWORD', 'JWT_SECRET'];
    samples.forEach((s, i) => writeFileSync(join(dir, 'a', `f${i}.js`), `x="${s}"`));
    const hits = scanDir(dir) as { file: string; rule: string }[];
    expect(new Set(hits.map((h) => h.rule)).size).toBe(RULES.length);
    rmSync(dir, { recursive: true, force: true });
  });

  it('builds the site and finds no secrets in dist/', () => {
    const r = spawnSync('node', ['scripts/check-bundle.mjs'], { encoding: 'utf8' });
    expect(r.stderr + r.stdout).toContain('bundle clean');
    expect(r.status).toBe(0);
  }, 300_000);
});
