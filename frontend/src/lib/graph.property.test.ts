import { describe, expect, it } from 'vitest';
import fc from 'fast-check';
import {
  EDGE_TYPES,
  filterGraph,
  type EdgeData,
  type GraphElements,
  type GraphFilters,
  type NodeData,
} from './graph';

/**
 * Feature: necromarc, Property 21: Graph filtering
 * **Validates: Requirements 12.4, 12.5**
 */

const word = fc.constantFrom('alpha', 'Beta', 'gamma', 'DELTA', 'omega', 'sigma');
const text = fc.array(word, { minLength: 1, maxLength: 3 }).map((w) => w.join(' '));
const lc = (s: string | null | undefined) => (s ?? '').toLowerCase();

const elementsArb: fc.Arbitrary<GraphElements> = fc
  .record({
    books: fc.array(
      fc.record({
        title: text,
        author: fc.option(text, { nil: null }),
        year: fc.option(fc.integer({ min: 1400, max: 2000 }), { nil: null }),
        subjects: fc.array(text, { maxLength: 3 }),
      }),
      { maxLength: 8 },
    ),
    authors: fc.integer({ min: 0, max: 4 }),
    subjects: fc.integer({ min: 0, max: 4 }),
  })
  .chain(({ books, authors, subjects }) => {
    const nodes: { data: NodeData }[] = [];
    books.forEach((b, i) =>
      nodes.push({ data: { id: `b${i}`, label: b.title, kind: 'book', ...b } }),
    );
    for (let i = 0; i < authors; i++)
      nodes.push({ data: { id: `a${i}`, label: `author ${i}`, kind: 'author' } });
    for (let i = 0; i < subjects; i++)
      nodes.push({ data: { id: `s${i}`, label: `subject ${i}`, kind: 'subject' } });
    const ids = nodes.map((n) => n.data.id);
    const edgeArb = ids.length
      ? fc.array(
          fc.record({
            source: fc.constantFrom(...ids),
            target: fc.constantFrom(...ids),
            edgeType: fc.constantFrom(...EDGE_TYPES),
          }),
          { maxLength: 15 },
        )
      : fc.constant([]);
    return edgeArb.map((es) => ({
      nodes,
      edges: es.map((e, i) => ({ data: { id: `e${i}`, ...e } as EdgeData })),
    }));
  });

const filtersArb: fc.Arbitrary<GraphFilters> = fc.record(
  {
    q: fc.oneof(word, fc.constant('')),
    title: word,
    author: word,
    topic: word,
    yearFrom: fc.option(fc.integer({ min: 1400, max: 2000 }), { nil: null }),
    yearTo: fc.option(fc.integer({ min: 1400, max: 2000 }), { nil: null }),
    edgeTypes: fc.subarray([...EDGE_TYPES]),
  },
  { requiredKeys: [] },
);

/** Independent oracle for book matching (inputs are ASCII, so lowercase suffices). */
function oracleBook(d: NodeData, f: GraphFilters): boolean {
  const subs = d.subjects ?? [];
  if (f.q && !(lc(d.title).includes(lc(f.q)) || lc(d.author).includes(lc(f.q)) ||
      subs.some((s) => lc(s).includes(lc(f.q))))) return false;
  if (f.title && !lc(d.title).includes(lc(f.title))) return false;
  if (f.author && !lc(d.author).includes(lc(f.author))) return false;
  if (f.topic && !subs.some((s) => lc(s).includes(lc(f.topic)))) return false;
  if (typeof f.yearFrom === 'number' || typeof f.yearTo === 'number') {
    if (typeof d.year !== 'number') return false;
    if (typeof f.yearFrom === 'number' && d.year < f.yearFrom) return false;
    if (typeof f.yearTo === 'number' && d.year > f.yearTo) return false;
  }
  return true;
}

describe('Property 21: Graph filtering', () => {
  it('returns matching books, linked authors/subjects, and edges with both endpoints shown', () => {
    fc.assert(
      fc.property(elementsArb, filtersArb, (els, f) => {
        const out = filterGraph(els, f);
        const kind = new Map(els.nodes.map((n) => [n.data.id, n.data.kind]));
        const books = new Set(
          els.nodes.filter((n) => n.data.kind === 'book' && oracleBook(n.data, f)).map((n) => n.data.id),
        );
        const expectedNodes = new Set(books);
        for (const e of els.edges) {
          const { source, target } = e.data;
          if (books.has(source) && kind.get(target) !== 'book') expectedNodes.add(target);
          if (books.has(target) && kind.get(source) !== 'book') expectedNodes.add(source);
        }
        const types = f.edgeTypes?.length ? new Set(f.edgeTypes) : null;
        const expectedEdges = els.edges
          .filter(
            (e) =>
              expectedNodes.has(e.data.source) &&
              expectedNodes.has(e.data.target) &&
              (!types || types.has(e.data.edgeType)),
          )
          .map((e) => e.data.id);

        expect(new Set(out.nodes.map((n) => n.data.id))).toEqual(expectedNodes);
        expect(out.nodes.length).toBe(expectedNodes.size);
        expect(out.edges.map((e) => e.data.id)).toEqual(expectedEdges);
      }),
      { numRuns: 200 },
    );
  });

  it('clearing all filters returns the original graph', () => {
    fc.assert(
      fc.property(elementsArb, fc.constantFrom({}, { q: '' }, { q: '  ', edgeTypes: [] }), (els, f) => {
        const out = filterGraph(els, f);
        expect(out.nodes).toEqual(els.nodes);
        expect(out.edges).toEqual(els.edges);
      }),
      { numRuns: 100 },
    );
  });
});
