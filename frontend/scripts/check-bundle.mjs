// Bundle secret gate (Requirement 18): build the site, then scan dist/ for secret patterns.
// Prints file path and rule name only, never the matched text. Exits non-zero on a hit.
// Usage: node scripts/check-bundle.mjs [--no-build]
import { spawnSync } from 'node:child_process';
import { readdirSync, readFileSync, rmSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const dist = join(root, 'dist');

export const RULES = [
  ['openrouter-key', /sk-or[-]/],
  ['google-api-key', /AI[z]a/],
  ['jwt', /ey[J][A-Za-z0-9_-]{5,}/],
  ['service_role', /service_role/i],
  ['SUPABASE_SERVICE_ROLE_KEY', /SUPABASE_SERVICE_ROLE_KEY/],
  ['supabase-host', /supabase\.(co|in|net)\b/i],
  ['JUDGE_PASSWORD', /JUDGE_PASSWORD/],
  ['JWT_SECRET', /JWT_SECRET/],
];

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

/** Returns [{file, rule}] for every rule matched in every text-like file under `dir`. */
export function scanDir(dir) {
  const hits = [];
  for (const file of walk(dir)) {
    if (/\.(woff2?|ttf|otf|png|jpe?g|gif|webp|ico|mrc)$/i.test(file)) continue;
    const text = readFileSync(file, 'latin1');
    for (const [rule, re] of RULES) if (re.test(text)) hits.push({ file: relative(root, file), rule });
  }
  return hits;
}

export function build() {
  rmSync(dist, { recursive: true, force: true });
  const r = spawnSync('npx', ['astro', 'build'], {
    cwd: root,
    stdio: ['ignore', 'ignore', 'inherit'],
    env: {
      ...process.env,
      PUBLIC_BASE_PATH: '/necromarc',
      PUBLIC_API_URL: 'https://3aai.in/necromarc/api',
    },
  });
  if (r.status !== 0) {
    console.error('build failed');
    process.exit(r.status ?? 1);
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  if (!process.argv.includes('--no-build')) build();
  const hits = scanDir(dist);
  for (const h of hits) console.error(`${h.file}: ${h.rule}`);
  if (hits.length > 0) process.exit(1);
  console.log('bundle clean');
}
