import { describe, expect, it } from 'vitest';
import { THEME } from './theme';

function lin(c: number): number {
  const s = c / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}
export function luminance(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  return 0.2126 * lin((n >> 16) & 255) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255);
}
export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe('contrast calculator', () => {
  it('matches known WCAG values', () => {
    expect(contrast('#000000', '#FFFFFF')).toBeCloseTo(21, 5);
    expect(contrast('#777777', '#777777')).toBeCloseTo(1, 5);
  });
});

describe('theme token contrast (11.12)', () => {
  const textPairs: [string, string, string][] = [
    ['parchment on ink', THEME.parchment, THEME.ink],
    ['gold on ink', THEME.gold, THEME.ink],
    ['decay-red on ink', THEME.decayRed, THEME.ink],
    ['ai-violet on ink', THEME.aiViolet, THEME.ink],
    ['phosphor on ink', THEME.phosphor, THEME.ink],
    ['phosphor on terminal-bg', THEME.phosphor, THEME.terminalBg],
    ['decay-red on terminal-bg', THEME.decayRed, THEME.terminalBg],
    ['ai-violet on terminal-bg', THEME.aiViolet, THEME.terminalBg],
    ['parchment on terminal-bg', THEME.parchment, THEME.terminalBg],
  ];
  it.each(textPairs)('%s >= 4.5:1', (_n, fg, bg) => {
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(4.5);
  });

  const uiPairs: [string, string, string][] = [
    ['gold border on ink', THEME.gold, THEME.ink],
    ['phosphor border on ink', THEME.phosphor, THEME.ink],
    ['phosphor meter on ink', THEME.phosphor, THEME.ink],
    ['decay-red marker on terminal-bg', THEME.decayRed, THEME.terminalBg],
    ['ai-violet border on terminal-bg', THEME.aiViolet, THEME.terminalBg],
  ];
  it.each(uiPairs)('%s >= 3:1', (_n, fg, bg) => {
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(3);
  });
});
