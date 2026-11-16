import { describe, expect, it, vi } from 'vitest';
import { handleTrapKey, nextFocusIndex } from './focusTrap';

describe('nextFocusIndex', () => {
  it('wraps forward and backward', () => {
    expect(nextFocusIndex(3, 2, false)).toBe(0);
    expect(nextFocusIndex(3, 0, true)).toBe(2);
    expect(nextFocusIndex(3, 0, false)).toBe(1);
    expect(nextFocusIndex(3, 2, true)).toBe(1);
  });
  it('enters the trap from outside', () => {
    expect(nextFocusIndex(3, -1, false)).toBe(0);
    expect(nextFocusIndex(3, -1, true)).toBe(2);
  });
  it('returns -1 with nothing focusable', () => {
    expect(nextFocusIndex(0, -1, false)).toBe(-1);
  });
});

function fakeItem() {
  return { disabled: false, hidden: false, type: 'text', closest: () => null, focus: vi.fn() };
}

describe('handleTrapKey', () => {
  const items = [fakeItem(), fakeItem(), fakeItem()];
  const container = { querySelectorAll: () => items } as unknown as HTMLElement;
  const ev = (key: string, shiftKey = false) => ({ key, shiftKey, preventDefault: vi.fn() });

  it('Tab on the last item focuses the first', () => {
    const e = ev('Tab');
    expect(handleTrapKey(e, container, items[2] as unknown as Element, () => {})).toBe(true);
    expect(items[0].focus).toHaveBeenCalled();
    expect(e.preventDefault).toHaveBeenCalled();
  });
  it('Shift+Tab on the first item focuses the last', () => {
    handleTrapKey(ev('Tab', true), container, items[0] as unknown as Element, () => {});
    expect(items[2].focus).toHaveBeenCalled();
  });
  it('skips disabled items', () => {
    const list = [fakeItem(), fakeItem(), fakeItem()];
    list[1].disabled = true;
    const c = { querySelectorAll: () => list } as unknown as HTMLElement;
    handleTrapKey(ev('Tab'), c, list[0] as unknown as Element, () => {});
    expect(list[1].focus).not.toHaveBeenCalled();
    expect(list[2].focus).toHaveBeenCalledOnce();
  });
  it('Escape calls onEscape', () => {
    const onEscape = vi.fn();
    expect(handleTrapKey(ev('Escape'), container, null, onEscape)).toBe(true);
    expect(onEscape).toHaveBeenCalledOnce();
  });
  it('ignores other keys', () => {
    expect(handleTrapKey(ev('a'), container, null, () => {})).toBe(false);
  });
});
