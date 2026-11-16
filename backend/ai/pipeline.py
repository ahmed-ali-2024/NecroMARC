"""Resurrection pipeline (Requirements 3, 4, 5). Callable contract: ``pipeline(records) -> results``.

Per record: decay, LLM, schema validation (inside the client), healing, vitality, embedding
(a failure stores ``embedding = null``), edge candidates and semantic matches, atomic
``store_resurrection``. A failed LLM stage goes through ``store_failure`` with raw data untouched.
"""
from __future__ import annotations
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from backend.ai.gemini import EmbeddingVector, build_embedding_input
from backend.ai.openrouter import Failure
from backend.db.client import RecordAlreadyResurrected
from backend.decay.rules import calculate_decay
from backend.decay.vitality import apply_resurrection, vitality_score
from backend.graph.edges import EdgeCandidate, compute_edges
from backend.graph.normalize import extract_year, normalize_text
from backend.parser.model import ParsedRecord

log = logging.getLogger(__name__)
MAX_WORKERS = 5
SOURCE = "upload"
SEMANTIC_MATCH_COUNT = 50


def _error(code: str, message: str) -> Dict[str, Any]:
    return {"status": "failure", "error": {"code": code, "message": message}}


def _first_subfield(rec: ParsedRecord, tag: str, code: str) -> Optional[str]:
    for f in rec.fields:
        if f.tag == tag:
            for sf in f.subfields:
                if sf.code == code and sf.value and sf.value.strip():
                    return sf.value.strip()
    return None


class ResurrectionPipeline:
    def __init__(self, repo_getter: Callable[[], Any], llm: Any, embedder: Any,
                 similarity_threshold: float = 0.75,
                 current_year: Optional[Callable[[], int]] = None,
                 max_workers: int = MAX_WORKERS, source: str = SOURCE,
                 semantic_edge_max: int = SEMANTIC_MATCH_COUNT):
        self._repo_getter = repo_getter
        self._llm = llm
        self._embedder = embedder
        self._threshold = similarity_threshold
        self._year = current_year or (lambda: datetime.datetime.now(datetime.timezone.utc).year)
        self._workers = max_workers
        self._source = source
        self._edge_max = semantic_edge_max

    def __call__(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not records:
            return []
        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            futures = [pool.submit(self._safe, r) for r in records]
            return [f.result() for f in futures]  # submitted order

    def _safe(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.process(raw)
        except Exception:  # one record never takes the batch down; no detail leaks
            log.exception("resurrection failed unexpectedly")
            return _error("STORE_FAILED", "The record could not be stored.")

    def process(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        from backend.app.routes.resurrect import control_number_of
        from backend.app.routes.export import to_parsed
        repo = self._repo_getter()
        year_now = self._year()
        rec = to_parsed(raw)
        control = control_number_of(raw)
        decay = calculate_decay(rec, year_now)
        breakdown = [{"rule": e.rule, "points": e.points} for e in decay.breakdown]
        title = rec.titles[0].title if rec.titles else None
        author = rec.authors[0].name if rec.authors else None

        outcome = self._llm.resurrect(rec)
        if isinstance(outcome, Failure):
            code = "VALIDATION_FAILED" if outcome.reason == "validation_failed" else "ALL_MODELS_UNAVAILABLE"
            try:
                repo.store_failure({"source": self._source, "control_number": control,
                                    "raw_record": raw, "decay_score": decay.score,
                                    "decay_breakdown": breakdown, "title": title, "author": author,
                                    "failure_reason": outcome.reason})
            except Exception:
                log.exception("store_failure failed")
            return _error(code, "The record could not be resurrected.")

        result = outcome.result
        healed = apply_resurrection(rec, result, year_now)
        vitality = vitality_score(healed, year_now)
        h_title = healed.titles[0].title if healed.titles else title
        h_author = healed.authors[0].name if healed.authors else author
        subjects = [s.term for s in healed.subjects if s.term]
        subjects_norm = sorted({n for n in (normalize_text(s) for s in subjects) if n})
        author_norm = normalize_text(h_author) if h_author else None
        author_norm = author_norm or None
        pub_c = [p.date for p in healed.publications if p.date]
        year = extract_year(pub_c)
        if year is None:
            year = result.get("normalized_year")

        text = build_embedding_input(h_title, h_author, result.get("healed_summary"),
                                     result.get("inferred_subjects"))
        emb = self._embedder.embed(text, "RETRIEVAL_DOCUMENT")
        vector = emb.values if isinstance(emb, EmbeddingVector) else None

        edges: List[Dict[str, Any]] = []
        try:
            edges = self._edges(repo, author_norm, subjects_norm, year, vector)
        except Exception:
            log.exception("edge computation failed")  # record still stored, without edges

        payload = {"record": {
            "source": self._source, "control_number": control, "raw_record": raw,
            "healed_record": _healed_dict(healed), "resurrection": result,
            "decay_score": decay.score, "decay_breakdown": breakdown,
            "vitality_score": vitality, "title": h_title, "author": h_author, "year": year,
            "language_name": result.get("language_name"), "author_norm": author_norm,
            "subjects": subjects, "subjects_norm": subjects_norm, "embedding": vector},
            "edges": edges}
        try:
            rid = repo.store_resurrection(payload)
        except RecordAlreadyResurrected:
            return _error("DUPLICATE_RESURRECTED", "This record has already been resurrected.")
        except Exception:
            log.exception("store_resurrection failed")
            return _error("STORE_FAILED", "The record could not be stored.")
        from backend.app.routes.records import record_detail
        row = repo.get(str(rid))
        return {"status": "success", "id": str(rid),
                "record": record_detail(row) if row else None,
                "embedding_stored": vector is not None}

    def _edges(self, repo, author_norm, subjects_norm, year, vector) -> List[Dict[str, Any]]:
        from uuid import UUID
        d_from = d_to = None
        if year is not None:
            d_from = year // 10 * 10
            d_to = d_from + 9
        rows = repo.edge_candidates(None, author_norm, subjects_norm, d_from, d_to)
        existing = [EdgeCandidate(UUID(str(r["id"])), r.get("author_norm"),
                                  frozenset(r.get("subjects_norm") or ()), r.get("year"))
                    for r in rows]
        semantic: Dict[Any, float] = {}
        if vector is not None:
            for m in repo.search_semantic(vector, self._edge_max):
                semantic[UUID(str(m["id"]))] = float(m["similarity"])
        new = EdgeCandidate(UUID(int=0), author_norm, frozenset(subjects_norm), year)
        specs = compute_edges(new, existing, semantic, self._threshold)
        return [{"other_id": str(s.other_id), "edge_type": s.edge_type, "weight": s.weight}
                for s in specs]


def _healed_dict(healed: ParsedRecord) -> Dict[str, Any]:
    from backend.app.routes.upload import raw_record_dict
    return raw_record_dict(healed)


def build_pipeline(settings, repo_getter: Callable[[], Any], http=None,
                   source: str = SOURCE) -> ResurrectionPipeline:
    from backend.ai.gemini import GeminiEmbeddingClient
    from backend.ai.openrouter import OpenRouterClient
    llm = OpenRouterClient(settings.openrouter_api_key, settings.openrouter_model,
                           settings.openrouter_fallback_models, http=http)
    embedder = GeminiEmbeddingClient(settings.gemini_api_key, settings.gemini_embedding_model,
                                     http_client=http)
    return ResurrectionPipeline(repo_getter, llm, embedder, settings.similarity_threshold,
                               semantic_edge_max=settings.semantic_edge_max, source=source)
