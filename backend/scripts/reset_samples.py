"""Refill the sample pool: ``python -m backend.scripts.reset_samples [--confirm]`` (Req 20.9-20.11).

Without ``--confirm`` this is a dry run: it prints how many ``source = 'sample'`` records exist
per status and how many knowledge edges a reset would remove, and deletes nothing.

With ``--confirm`` it calls ``reset_sample_records()``, which deletes only ``source = 'sample'``
rows (their edges go through the foreign-key cascade) and leaves every other record unchanged.

Exit codes: 0 success, 1 database error, 2 configuration error. Secret values are never printed.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Optional, Sequence, TextIO


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m backend.scripts.reset_samples",
                                description="Delete resurrected sample-pool records so the pool can be reused.")
    p.add_argument("--confirm", action="store_true",
                   help="Actually delete the source='sample' records. Without it, only a preview is shown.")
    return p


def _preview_lines(rows: Sequence[dict]) -> list[str]:
    if not rows:
        return ["Sample records in the archive: 0."]
    total = sum(int(r.get("records") or 0) for r in rows)
    edges = int(rows[0].get("edges") or 0)
    lines = [f"Sample records in the archive: {total}."]
    lines += [f"  {r.get('status')}: {int(r.get('records') or 0)}" for r in rows]
    lines.append(f"Knowledge edges that a reset would remove: {edges}.")
    return lines


def run(repo: Any, confirm: bool, out: Optional[TextIO] = None) -> int:
    from backend.db.client import DatabaseError, DatabaseUnavailable

    out = out if out is not None else sys.stdout

    try:
        rows = repo.preview_sample_reset()
        for line in _preview_lines(rows):
            print(line, file=out)
        if not confirm:
            print("Dry run: nothing was deleted. Re-run with --confirm to delete only source='sample' records.",
                  file=out)
            return 0
        deleted = repo.reset_sample_records()
    except (DatabaseUnavailable, DatabaseError) as exc:
        print(f"database error: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"Deleted {deleted} sample record(s). Other archive records were not touched.", file=out)
    return 0


def main(argv: Optional[Sequence[str]] = None, env: Any = None, repo: Any = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    if env is None:
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

    if repo is None:
        from backend.app.logging_utils import install_redaction
        from backend.db.client import PostgrestClient
        from backend.db.records import RecordsRepo

        install_redaction(settings.secret_values())
        repo = RecordsRepo(PostgrestClient.from_settings(settings))
    return run(repo, args.confirm)


if __name__ == "__main__":
    sys.exit(main())
