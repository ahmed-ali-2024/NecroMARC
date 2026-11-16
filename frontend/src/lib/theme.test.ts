import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { THEME } from './theme';

const css = readFileSync(new URL('../styles/global.css', import.meta.url), 'utf8');

describe('theme tokens', () => {
  it.each([
    ['ink', THEME.ink],
    ['parchment', THEME.parchment],
    ['gold', THEME.gold],
    ['terminal-bg', THEME.terminalBg],
    ['phosphor', THEME.phosphor],
    ['decay-red', THEME.decayRed],
    ['ai-violet', THEME.aiViolet],
  ])('global.css defines --color-%s', (name, value) => {
    expect(css.toLowerCase()).toContain(`--color-${name}: ${value.toLowerCase()};`);
  });

  it('self-hosts an Arabic font without third-party CDNs', () => {
    expect(css).toContain('@fontsource/amiri');
    expect(css).not.toMatch(/https?:\/\//);
  });
});
