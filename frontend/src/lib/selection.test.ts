import { describe, expect, it } from 'vitest';
import fc from 'fast-check';
import { filterItems, paginate, selectTopDecay, sortItems, toggleSelection } from './selection';

const item = fc.record({
  title: fc.option(fc.string({ maxLength: 12 }), { nil: null }),
  control_number: fc.option(fc.string({ maxLength: 8 }), { nil: null }),
  decay: fc.record({ score: fc.integer({ min: 0, max: 100 }) }),
});
const items = fc.array(item, { maxLength: 40 });

describe('selection unit', () => {
  it('rejects a sixth selection and keeps the set', () => {
    expect(toggleSelection([0, 1, 2, 3, 4], 5, 5)).toEqual({ selected: [0, 1, 2, 3, 4], rejected: true });
    expect(toggleSelection([0, 1, 2, 3, 4], 2, 5)).toEqual({ selected: [0, 1, 3, 4], rejected: false });
  });
  it('filters accent- and case-insensitively on title and control number', () => {
    const list = [
      { title: 'Café Société', control_number: 'A1', decay: { score: 1 } },
      { title: null, control_number: 'XYZ-9', decay: { score: 2 } },
    ];
    expect(filterItems(list, 'CAFE')).toEqual([list[0]]);
    expect(filterItems(list, 'xyz')).toEqual([list[1]]);
    expect(filterItems(list, '')).toEqual(list);
  });
  it('sorts by decay descending, original keeps order', () => {
    const list = [{ decay: { score: 1 } }, { decay: { score: 9 } }];
    expect(sortItems(list, 'decay').map((x) => x.decay.score)).toEqual([9, 1]);
    expect(sortItems(list, 'original')).toEqual(list);
  });
  it('paginate clamps pages', () => {
    expect(paginate([1, 2, 3], 2, 2)).toEqual([3]);
    expect(paginate([1, 2, 3], 99, 2)).toEqual([3]);
    expect(paginate([], 1, 2)).toEqual([]);
  });
});

describe('selection properties', () => {
  it('a selection never exceeds max', () => {
    fc.assert(
      fc.property(fc.array(fc.integer({ min: 0, max: 30 }), { maxLength: 100 }), (toggles) => {
        let sel: number[] = [];
        for (const i of toggles) sel = toggleSelection(sel, i, 5).selected;
        expect(sel.length).toBeLessThanOrEqual(5);
      }),
    );
  });

  it('toggling an index twice restores the selection', () => {
    fc.assert(
      fc.property(
        fc.uniqueArray(fc.integer({ min: 0, max: 30 }), { maxLength: 4 }),
        fc.integer({ min: 0, max: 30 }),
        (start, idx) => {
          const base = toggleSelection(start, -1, 5).selected; // normalised (sorted)
          const once = toggleSelection(base, idx, 5);
          const twice = toggleSelection(once.selected, idx, 5);
          expect(twice.selected).toEqual(base);
        },
      ),
    );
  });

  it('paginate covers every item exactly once', () => {
    fc.assert(
      fc.property(fc.array(fc.integer(), { maxLength: 60 }), fc.integer({ min: 1, max: 12 }), (list, size) => {
        const pages = Math.max(1, Math.ceil(list.length / size));
        const all: number[] = [];
        for (let p = 1; p <= pages; p++) all.push(...paginate(list, p, size));
        expect(all).toEqual(list);
      }),
    );
  });

  it('filterItems returns a subset of its input', () => {
    fc.assert(
      fc.property(items, fc.string({ maxLength: 4 }), (list, q) => {
        const out = filterItems(list, q);
        expect(out.length).toBeLessThanOrEqual(list.length);
        for (const o of out) expect(list).toContain(o);
      }),
    );
  });

  it('selectTopDecay returns the highest scores in descending order', () => {
    fc.assert(
      fc.property(items, fc.integer({ min: 0, max: 10 }), (list, n) => {
        const idx = selectTopDecay(list, n);
        expect(idx.length).toBe(Math.min(n, list.length));
        expect(new Set(idx).size).toBe(idx.length);
        const scores = idx.map((i) => list[i].decay.score);
        for (let k = 1; k < scores.length; k++) expect(scores[k - 1]).toBeGreaterThanOrEqual(scores[k]);
        const rest = list.map((_, i) => i).filter((i) => !idx.includes(i));
        const min = scores.length ? Math.min(...scores) : Infinity;
        for (const i of rest) expect(list[i].decay.score).toBeLessThanOrEqual(min);
      }),
    );
  });
});
