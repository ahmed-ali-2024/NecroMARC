import { describe, it, expect } from 'vitest';
import {
  filterGraph,
  neighborIds,
  buildStylesheet,
  NODE_STYLE,
  EDGE_STYLE,
  EDGE_TYPES,
  NODE_KINDS,
  type GraphElements,
} from './graph';

const els: GraphElements = {
  nodes: [
    { data: { id: 'b:1', label: 'Alpha', kind: 'book', title: 'Alpha', author: 'Zed Écrivain', year: 1850, subjects: ['Alchemy'] } },
    { data: { id: 'b:2', label: 'Beta', kind: 'book', title: 'Beta', author: 'Other', year: 1990, subjects: ['Maps'] } },
    { data: { id: 'b:3', label: 'Gamma', kind: 'book', title: 'Gamma', author: null, year: null, subjects: [] } },
    { data: { id: 'a:zed', label: 'Zed Écrivain', kind: 'author' } },
    { data: { id: 'a:other', label: 'Other', kind: 'author' } },
    { data: { id: 's:alchemy', label: 'Alchemy', kind: 'subject' } },
  ],
  edges: [
    { data: { id: 'e1', source: 'b:1', target: 'b:2', edgeType: 'SAME_ERA' } },
    { data: { id: 'e2', source: 'b:2', target: 'b:3', edgeType: 'SHARED_SUBJECT' } },
    { data: { id: 'x1', source: 'b:1', target: 'a:zed', edgeType: 'AUTHORED_BY', structural: true } },
    { data: { id: 'x2', source: 'b:2', target: 'a:other', edgeType: 'AUTHORED_BY', structural: true } },
    { data: { id: 'x3', source: 'b:1', target: 's:alchemy', edgeType: 'HAS_SUBJECT', structural: true } },
  ],
};
const ids = (r: { data: { id: string } }[]) => r.map((x) => x.data.id);

describe('filterGraph', () => {
  it('returns original elements when no filter is active', () => {
    const r = filterGraph(els, { q: '  ', yearFrom: null });
    expect(r.nodes).toBe(els.nodes);
    expect(r.edges).toBe(els.edges);
  });

  it('matches q accent-insensitively and keeps linked author/subject nodes', () => {
    const r = filterGraph(els, { q: 'ecrivain' });
    expect(ids(r.nodes).sort()).toEqual(['a:zed', 'b:1', 's:alchemy']);
    expect(ids(r.edges).sort()).toEqual(['x1', 'x3']);
  });

  it('filters by inclusive year range and excludes books without a year', () => {
    const r = filterGraph(els, { yearFrom: 1850, yearTo: 1990 });
    expect(ids(r.nodes).filter((i) => i.startsWith('b:')).sort()).toEqual(['b:1', 'b:2']);
    expect(ids(r.edges)).toContain('e1');
    expect(ids(r.edges)).not.toContain('e2');
  });

  it('filters by topic', () => {
    const r = filterGraph(els, { topic: 'maps' });
    expect(ids(r.nodes).sort()).toEqual(['a:other', 'b:2']);
  });

  it('combines filters with AND', () => {
    const r = filterGraph(els, { author: 'zed', topic: 'maps' });
    expect(r.nodes).toEqual([]);
    expect(r.edges).toEqual([]);
  });

  it('restricts edges by type', () => {
    const r = filterGraph(els, { edgeTypes: ['SAME_ERA'] });
    expect(ids(r.edges)).toEqual(['e1']);
  });
});

describe('neighborIds', () => {
  it('lists directly connected nodes', () => {
    expect([...neighborIds(els, 'b:1')].sort()).toEqual(['a:zed', 'b:2', 's:alchemy']);
  });
});

describe('styles', () => {
  it('uses distinct node shapes/colors and distinct edge styles', () => {
    expect(new Set(NODE_KINDS.map((k) => NODE_STYLE[k].shape)).size).toBe(3);
    const combos = EDGE_TYPES.map((t) => `${EDGE_STYLE[t].color}|${EDGE_STYLE[t].line}`);
    expect(new Set(combos).size).toBe(EDGE_TYPES.length);
  });

  it('stylesheet covers every kind and edge type', () => {
    const sels = buildStylesheet().map((s) => s.selector);
    for (const k of NODE_KINDS) expect(sels).toContain(`node[kind = "${k}"]`);
    for (const t of EDGE_TYPES) expect(sels).toContain(`edge[edgeType = "${t}"]`);
  });
});
