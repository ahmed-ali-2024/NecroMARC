// @vitest-environment happy-dom
import { describe, expect, it, vi } from 'vitest';
import type { RawRecord, ResurrectResponse } from './api';
import { renderRecord, showFailure, showSuccess } from './terminal';
import { renderCard, runResurrection } from './card';
import type { CardModel } from './card';

const raw: RawRecord = {
  leader: '00000nam a2200000 a 4500',
  fields: [
    { tag: '245', ind1: '1', ind2: '0', subfields: [['a', 'T']] },
    { tag: '700', subfields: [['a', 'Y']], ai: true },
  ],
};

describe('terminal rendering', () => {
  it('marks missing lines, labels the rule, and labels AI values', () => {
    const list = document.createElement('ol');
    renderRecord(list, raw, [{ rule: 'missing_520', points: 30 }]);
    const lis = [...list.querySelectorAll('li')];
    expect(lis.every((l) => l.getAttribute('dir') === 'ltr')).toBe(true);
    const missing = lis.find((l) => l.textContent?.includes('=520'))!;
    expect(missing.classList.contains('terminal-decay')).toBe(true);
    expect(missing.querySelector('.terminal-decay-label')).not.toBeNull();
    expect(lis.find((l) => l.textContent?.includes('=650'))!.classList.contains('terminal-decay')).toBe(true);
    expect(list.querySelectorAll('.terminal-ai').length).toBe(1);
  });
  it('appends success and failure lines', () => {
    const list = document.createElement('ol');
    showSuccess(list, 'ok');
    showFailure(list, 'bad');
    expect(list.querySelector('.terminal-success')?.textContent).toBe('ok');
    expect(list.querySelector('.terminal-failure')?.textContent).toBe('bad');
  });
});

describe('card states', () => {
  it('renders AI label and before/after meters', () => {
    const host = document.createElement('div');
    const m: CardModel = {
      id: 'x', summary: 'S', subjects: ['a'], language: 'Arabic', year: 1900, decayScore: 65,
      breakdown: [], vitalityBefore: 35, vitalityAfter: 85, aiTags: ['520'],
    };
    renderCard(host, m);
    expect(host.querySelectorAll('.card-ai').length).toBeGreaterThan(0);
    expect([...host.querySelectorAll('[role=meter]')].map((x) => x.getAttribute('aria-valuenow'))).toEqual(['35', '85']);
  });
  it('shows pending synchronously, then failure with retry', async () => {
    const host = document.createElement('div');
    const send = vi.fn(() => Promise.reject(new Error('boom')) as Promise<ResurrectResponse>);
    const onFailure = vi.fn();
    runResurrection(host, [raw], send, { onSuccess: vi.fn(), onFailure }, 1000);
    expect(host.getAttribute('aria-busy')).toBe('true');
    expect(host.querySelector('[role=status]')).not.toBeNull();
    await vi.waitFor(() => expect(onFailure).toHaveBeenCalled());
    expect(host.hasAttribute('aria-busy')).toBe(false);
    expect(host.querySelector('[role=alert]')).not.toBeNull();
    host.querySelector<HTMLButtonElement>('.card-retry')!.click();
    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[1][0]).toBe(send.mock.calls[0][0]);
  });
});
