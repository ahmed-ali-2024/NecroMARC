"""Seed entry point: ``python -m backend.scripts.seed`` (local command line only, Req 15.2).

Fetches Gutenberg and LoC SRU records (one shared throttle, Req 15.3) plus the synthetic
set, parses them, and sends them through the resurrection pipeline in batches of at most 5.
Records already resurrected under the same (source, 001) are skipped untouched (Req 15.6).
Per-record failures are logged and counted, and processing continues (Req 15.7).
"""
from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Callable
from typing import Any

from backend.app.routes.resurrect import MAX_BATCH, control_number_of
from backend.app.routes.upload import raw_record_dict
from backend.parser.iso2709 import parse_iso2709
from backend.scripts.seed.report import SeedReport
from backend.scripts.seed.sources import SourceResult, Throttle, fetch_gutenberg, fetch_loc_sru
from backend.scripts.seed.synthetic import generate_synthetic

logger = logging.getLogger("necromarc.seed")

Pipeline = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


def _process_source(
    source: str,
    blobs: list[bytes],
    repo: Any,
    pipeline: Pipeline,
    report: SeedReport,
    seen: set[str],
) -> None:
    stats = report.stats(source)
    pending: list[tuple[str, dict[str, Any]]] = []  # (control_number, raw)

    for blob in blobs:
        parsed = parse_iso2709(blob)
        if not parsed.records:
            stats.failed += 1
            codes = ",".join(e.code for e in parsed.errors) or "NO_RECORDS"
            logger.error("seed failure source=%s 001=<unparseable> reason=%s", source, codes)
            continue
        for rec in parsed.records:
            raw = raw_record_dict(rec)
            cn = control_number_of(raw)
            if cn in seen or repo.exists(source, cn, "resurrected"):
                stats.skipped += 1
                continue
            seen.add(cn)
            pending.append((cn, raw))

    for i in range(0, len(pending), MAX_BATCH):
        batch = pending[i : i + MAX_BATCH]
        try:
            results = pipeline([raw for _, raw in batch])
        except Exception as exc:  # noqa: BLE001 - keep going after a whole-batch failure
            results = [{"status": "failure", "error": {"code": type(exc).__name__, "message": "batch error"}}] * len(batch)
        if len(results) != len(batch):
            results = list(results)[: len(batch)] + [
                {"status": "failure", "error": {"code": "MISSING_RESULT", "message": "no result"}}
            ] * (len(batch) - len(results))
        for (cn, raw), res in zip(batch, results):
            if res.get("status") == "success":
                stats.created += 1
                continue
            err = res.get("error") or {}
            reason = f"{err.get('code', 'UNKNOWN')}: {err.get('message', '')}".strip()
            stats.failed += 1
            logger.error("seed failure source=%s 001=%s reason=%s", source, cn, reason)
            _mark_failed(repo, source, cn, raw, str(err.get("code", "unknown")).lower())


def _mark_failed(repo: Any, source: str, cn: str, raw: dict[str, Any], reason: str) -> None:
    """Ensure the record carries status `failed` (the pipeline already does this for LLM failures)."""
    try:
        if repo.exists(source, cn):
            return
        repo.store_failure({"source": source, "control_number": cn, "raw_record": raw,
                            "failure_reason": reason, "decay_score": 0, "decay_breakdown": []})
    except Exception as exc:  # noqa: BLE001
        logger.error("could not mark failed source=%s 001=%s (%s)", source, cn, type(exc).__name__)


def run_seed(
    settings: Any,
    repo: Any,
    pipeline_factory: Callable[[str], Pipeline],
    *,
    client: Any = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> SeedReport:
    started = clock()
    report = SeedReport()
    throttle = Throttle(settings.seed_wait_seconds, sleep)  # shared by Gutenberg and LoC (Req 15.3)
    seen: dict[str, set[str]] = {}

    fetched: list[SourceResult] = [
        fetch_gutenberg(settings.gutenberg_marc_url_template, settings.seed_quota_gutenberg, throttle, client),
        fetch_loc_sru(settings.loc_sru_url, settings.seed_quota_loc, throttle, client),
    ]
    for res in fetched:
        if res.warning:
            report.warnings.append(f"shortfall {res.warning}")
    batches: list[tuple[str, list[bytes]]] = [(r.source, r.records) for r in fetched]
    synthetic = generate_synthetic(settings.synthetic_seed)[: settings.seed_quota_synthetic]
    if len(synthetic) < settings.seed_quota_synthetic:
        report.warnings.append(
            f"shortfall synthetic: {settings.seed_quota_synthetic - len(synthetic)} record(s) missing")
    batches.append(("synthetic", [s.data for s in synthetic]))

    for source, blobs in batches:
        _process_source(source, blobs, repo, pipeline_factory(source), report, seen.setdefault(source, set()))

    report.elapsed_seconds = clock() - started
    return report


def main(env: Any = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)
    except ImportError:
        pass
    from backend.app.config import ConfigError, load_settings

    try:
        settings = load_settings(env if env is not None else os.environ)
    except ConfigError as exc:
        for problem in exc.problems:  # names variables and rules, never values
            print(f"config error: {problem}", file=sys.stderr)
        return 2

    from backend.ai.pipeline import build_pipeline
    from backend.db.client import PostgrestClient
    from backend.db.records import RecordsRepo

    repo = RecordsRepo(PostgrestClient.from_settings(settings))
    report = run_seed(settings, repo, lambda src: build_pipeline(settings, lambda: repo, source=src))
    print(report.format())
    return 0


if __name__ == "__main__":
    sys.exit(main())
