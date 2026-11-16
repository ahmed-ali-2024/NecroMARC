import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const src = readFileSync(new URL('./index.astro', import.meta.url), 'utf8');
const markup = src.split('</BaseLayout>')[0];
const panel = readFileSync(new URL('../../components/TerminalPanel.astro', import.meta.url), 'utf8');

describe('chamber page structure', () => {
  it('stacks at 375px and splits side by side from md (11.9, 11.10)', () => {
    expect(markup).toMatch(/grid-cols-1 md:grid-cols-2/);
    expect(markup).toContain('min-w-0');
  });
  it('builds links from BASE_URL, never a hardcoded path', () => {
    expect(src).toContain('import.meta.env.BASE_URL');
    expect(src).toContain('href={`${base}/`}');
    expect(src).toContain('`${base}/chamber/?id=');
    expect(markup).not.toMatch(/href="\/[^"]*"/);
  });
  it('shows the Resurrect button only to a Judge', () => {
    expect(markup).toMatch(/id="chamber-resurrect" hidden/);
    expect(markup).toMatch(/id="chamber-guest" hidden/);
    expect(src).toContain('resBtn.hidden = !judge;');
    expect(src).toContain('guest.hidden = judge;');
  });
  it('uses logical spacing, not physical left/right (14.4)', () => {
    expect(markup).not.toMatch(/\b(?:ml|mr|pl|pr|left|right|text-left|text-right)-/);
  });
  it('isolates MARC text as LTR inside the terminal panel (11.4)', () => {
    expect(panel).toMatch(/class="terminal marc-text[^"]*"[^>]*dir="ltr"/);
    expect(panel).toContain('lang="und"');
  });
  it('lets the title follow its content direction', () => {
    expect(markup).toMatch(/id="chamber-title"[^>]*dir="auto"/);
  });
});
