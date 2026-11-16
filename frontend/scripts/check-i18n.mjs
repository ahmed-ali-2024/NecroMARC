import { readFileSync } from 'node:fs';
const load = (n) => Object.keys(JSON.parse(readFileSync(new URL(`../src/i18n/${n}.json`, import.meta.url), 'utf8')));
const en = new Set(load('en'));
const ar = new Set(load('ar'));
const missingAr = [...en].filter((k) => !ar.has(k));
const missingEn = [...ar].filter((k) => !en.has(k));
if (missingAr.length || missingEn.length) {
  console.error('i18n key mismatch', { missingInArabic: missingAr, missingInEnglish: missingEn });
  process.exit(1);
}
console.log(`i18n OK (${en.size} keys)`);
