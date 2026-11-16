/** Pure graph helpers: client-side filtering plus shared style/legend constants. */

export type NodeKind = 'book' | 'author' | 'subject';
export const NODE_KINDS: NodeKind[] = ['book', 'author', 'subject'];
export const EDGE_TYPES = [
  'SHARED_SUBJECT',
  'SAME_AUTHOR',
  'SAME_ERA',
  'SEMANTIC_SIMILARITY',
  'AUTHORED_BY',
  'HAS_SUBJECT',
] as const;
export type EdgeType = (typeof EDGE_TYPES)[number];

export const MIN_ZOOM = 0.1;
export const MAX_ZOOM = 5;
export const MAX_QUERY_LENGTH = 200;

export interface NodeData {
  id: string;
  label: string;
  kind: string;
  recordId?: string;
  title?: string;
  author?: string | null;
  year?: number | null;
  subjects?: string[];
}
export interface EdgeData {
  id: string;
  source: string;
  target: string;
  edgeType: string;
  weight?: number;
  structural?: boolean;
}
export interface GraphElements {
  nodes: { data: NodeData }[];
  edges: { data: EdgeData }[];
}

export interface GraphFilters {
  /** Free-text term matched against title, author, and subjects. */
  q?: string;
  title?: string;
  author?: string;
  /** Inclusive year range; either bound may be omitted. */
  yearFrom?: number | null;
  yearTo?: number | null;
  /** Subject/topic text matched against book subjects. */
  topic?: string;
  /** When non-empty, only edges of these types are shown. */
  edgeTypes?: string[];
}

export interface FilteredGraph {
  nodes: { data: NodeData }[];
  edges: { data: EdgeData }[];
}

/** NFKD, drop combining marks, casefold, collapse whitespace. */
export function norm(s: unknown): string {
  if (typeof s !== 'string') return '';
  return s
    .normalize('NFKD')
    .replace(/\p{Mn}/gu, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

function has(hay: unknown, needle: string): boolean {
  return norm(hay).includes(needle);
}

export function hasActiveFilters(f: GraphFilters): boolean {
  return (
    norm(f.q) !== '' ||
    norm(f.title) !== '' ||
    norm(f.author) !== '' ||
    norm(f.topic) !== '' ||
    typeof f.yearFrom === 'number' ||
    typeof f.yearTo === 'number' ||
    (f.edgeTypes?.length ?? 0) > 0
  );
}

function bookMatches(d: NodeData, f: GraphFilters): boolean {
  const q = norm(f.q).slice(0, MAX_QUERY_LENGTH);
  const title = norm(f.title);
  const author = norm(f.author);
  const topic = norm(f.topic);
  const subjects = Array.isArray(d.subjects) ? d.subjects : [];
  if (q) {
    const ok =
      has(d.title ?? d.label, q) || has(d.author, q) || subjects.some((s) => has(s, q));
    if (!ok) return false;
  }
  if (title && !has(d.title ?? d.label, title)) return false;
  if (author && !has(d.author, author)) return false;
  if (topic && !subjects.some((s) => has(s, topic))) return false;
  const hasFrom = typeof f.yearFrom === 'number';
  const hasTo = typeof f.yearTo === 'number';
  if (hasFrom || hasTo) {
    const y = d.year;
    if (typeof y !== 'number') return false;
    if (hasFrom && y < (f.yearFrom as number)) return false;
    if (hasTo && y > (f.yearTo as number)) return false;
  }
  return true;
}

/**
 * Book nodes shown iff they match every active filter. Author/subject nodes are
 * shown iff linked to a shown book. Edges shown iff both endpoints are shown
 * (and, when `edgeTypes` is set, the edge type is selected). With no active
 * filter the input is returned unchanged.
 */
export function filterGraph(elements: GraphElements, filters: GraphFilters): FilteredGraph {
  if (!hasActiveFilters(filters)) {
    return { nodes: elements.nodes, edges: elements.edges };
  }
  const kindOf = new Map<string, string>();
  const shownBooks = new Set<string>();
  for (const n of elements.nodes) {
    kindOf.set(n.data.id, n.data.kind);
    if (n.data.kind === 'book' && bookMatches(n.data, filters)) shownBooks.add(n.data.id);
  }
  const types = filters.edgeTypes?.length ? new Set(filters.edgeTypes) : null;
  const shown = new Set(shownBooks);
  // Non-book nodes are linked to at least one shown book by any edge.
  for (const e of elements.edges) {
    const { source, target } = e.data;
    if (shownBooks.has(source) && kindOf.has(target) && kindOf.get(target) !== 'book') {
      shown.add(target);
    } else if (shownBooks.has(target) && kindOf.has(source) && kindOf.get(source) !== 'book') {
      shown.add(source);
    }
  }
  const nodes = elements.nodes.filter((n) => shown.has(n.data.id));
  const edges = elements.edges.filter(
    (e) =>
      shown.has(e.data.source) &&
      shown.has(e.data.target) &&
      (!types || types.has(e.data.edgeType)),
  );
  return { nodes, edges };
}

/** Ids to show/hide, for batched visibility updates. */
export function visibleIds(filtered: FilteredGraph): Set<string> {
  const ids = new Set<string>();
  for (const n of filtered.nodes) ids.add(n.data.id);
  for (const e of filtered.edges) ids.add(e.data.id);
  return ids;
}

/** Node ids directly connected to `id` (for highlighting). */
export function neighborIds(elements: GraphElements, id: string): Set<string> {
  const out = new Set<string>();
  for (const e of elements.edges) {
    if (e.data.source === id) out.add(e.data.target);
    else if (e.data.target === id) out.add(e.data.source);
  }
  return out;
}

export const NODE_STYLE: Record<NodeKind, { shape: string; color: string }> = {
  book: { shape: 'ellipse', color: '#c9a227' },
  author: { shape: 'diamond', color: '#c9a6ff' },
  subject: { shape: 'hexagon', color: '#3fb8af' },
};

export const EDGE_STYLE: Record<EdgeType, { color: string; line: 'solid' | 'dashed' | 'dotted' }> = {
  SHARED_SUBJECT: { color: '#3fb8af', line: 'solid' },
  SAME_AUTHOR: { color: '#c9a6ff', line: 'dashed' },
  SAME_ERA: { color: '#eadfc8', line: 'dotted' },
  SEMANTIC_SIMILARITY: { color: '#4dff88', line: 'solid' },
  AUTHORED_BY: { color: '#8a7a55', line: 'dashed' },
  HAS_SUBJECT: { color: '#5b8f8b', line: 'dotted' },
};

/** Cytoscape stylesheet built from the style tables. */
export function buildStylesheet(): Record<string, unknown>[] {
  const sheet: Record<string, unknown>[] = [
    {
      selector: 'node',
      style: { label: 'data(label)', color: '#eadfc8', 'font-size': 10, width: 24, height: 24 },
    },
    { selector: 'edge', style: { width: 1.5, 'curve-style': 'bezier', opacity: 0.7 } },
    {
      selector: '.highlighted',
      style: { 'border-width': 3, 'border-color': '#ffffff', opacity: 1, 'z-index': 10 },
    },
    { selector: ':selected', style: { 'border-width': 3, 'border-color': '#ffffff' } },
  ];
  for (const k of NODE_KINDS) {
    sheet.push({
      selector: `node[kind = "${k}"]`,
      style: { shape: NODE_STYLE[k].shape, 'background-color': NODE_STYLE[k].color },
    });
  }
  for (const t of EDGE_TYPES) {
    sheet.push({
      selector: `edge[edgeType = "${t}"]`,
      style: { 'line-color': EDGE_STYLE[t].color, 'line-style': EDGE_STYLE[t].line },
    });
  }
  return sheet;
}
