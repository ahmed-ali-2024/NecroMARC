/** Pure helpers for choosing which uploaded records to resurrect. */

export interface SelectableItem {
  title?: string | null;
  control_number?: string | null;
  decay: { score: number };
}

export type SortMode = 'original' | 'decay';

export interface ToggleResult {
  /** Selected indexes, ascending and unique. */
  selected: number[];
  /** True when the toggle was refused because it would exceed `max`. */
  rejected: boolean;
}

/** Toggle `index` in `selected`. Adding beyond `max` is rejected and leaves the selection unchanged. */
export function toggleSelection(selected: readonly number[], index: number, max: number): ToggleResult {
  const current = [...new Set(selected)].sort((a, b) => a - b);
  if (current.includes(index)) {
    return { selected: current.filter((i) => i !== index), rejected: false };
  }
  if (current.length >= max) return { selected: current, rejected: true };
  return { selected: [...current, index].sort((a, b) => a - b), rejected: false };
}

/** Indexes of the `n` items with the highest decay score, highest first (ties keep original order). */
export function selectTopDecay(items: readonly SelectableItem[], n: number): number[] {
  return items
    .map((it, i) => ({ i, score: it.decay.score }))
    .sort((a, b) => b.score - a.score || a.i - b.i)
    .slice(0, Math.max(0, n))
    .map((x) => x.i);
}

function fold(s: string): string {
  return s.normalize('NFD').replace(/\p{M}+/gu, '').toLowerCase();
}

/** Keep items whose title or control number contains `query` (accent- and case-insensitive). */
export function filterItems<T extends Pick<SelectableItem, 'title' | 'control_number'>>(
  items: readonly T[],
  query: string,
): T[] {
  const q = fold(query.trim());
  if (!q) return [...items];
  return items.filter((it) => fold(it.title ?? '').includes(q) || fold(it.control_number ?? '').includes(q));
}

/** Return a sorted copy; 'original' keeps input order, 'decay' sorts by score descending (stable). */
export function sortItems<T extends Pick<SelectableItem, 'decay'>>(items: readonly T[], mode: SortMode): T[] {
  const copy = [...items];
  if (mode === 'decay') copy.sort((a, b) => b.decay.score - a.decay.score);
  return copy;
}

/** 1-based page slice. Out-of-range pages are clamped; empty lists yield an empty page. */
export function paginate<T>(list: readonly T[], page: number, size: number): T[] {
  const s = Math.max(1, Math.floor(size));
  const pages = Math.max(1, Math.ceil(list.length / s));
  const p = Math.min(Math.max(1, Math.floor(page) || 1), pages);
  return list.slice((p - 1) * s, p * s);
}
