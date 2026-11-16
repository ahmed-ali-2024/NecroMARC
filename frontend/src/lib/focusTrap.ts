/** Pure focus-trap helpers (Requirement 13.3). */

/** Index to focus after Tab / Shift+Tab, wrapping at both ends. -1 when nothing is focusable. */
export function nextFocusIndex(count: number, current: number, shift: boolean): number {
  if (count <= 0) return -1;
  if (current < 0 || current >= count) return shift ? count - 1 : 0;
  if (shift) return current === 0 ? count - 1 : current - 1;
  return current === count - 1 ? 0 : current + 1;
}

export const FOCUSABLE_SELECTOR =
  'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])';

/** Focusable, enabled, visible descendants of `container` in DOM order. */
export function focusableIn(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (el) =>
      !(el as HTMLButtonElement).disabled &&
      !el.hidden &&
      !el.closest('[hidden]') &&
      (el as HTMLInputElement).type !== 'hidden',
  );
}

/**
 * Handle a keydown inside a trapped container. Tab / Shift+Tab move focus within the
 * container with wrap-around; Escape calls `onEscape`. Returns true when handled.
 */
export function handleTrapKey(
  e: Pick<KeyboardEvent, 'key' | 'shiftKey' | 'preventDefault'>,
  container: HTMLElement,
  active: Element | null,
  onEscape: () => void,
): boolean {
  if (e.key === 'Escape') {
    e.preventDefault();
    onEscape();
    return true;
  }
  if (e.key !== 'Tab') return false;
  const items = focusableIn(container);
  e.preventDefault();
  const idx = nextFocusIndex(items.length, active ? items.indexOf(active as HTMLElement) : -1, e.shiftKey);
  if (idx >= 0) items[idx].focus();
  return true;
}
