"""Seed summary report (Req 15.10). Holds counts only; never secrets or record content."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SourceStats:
    source: str
    created: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass
class SeedReport:
    sources: list[SourceStats] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def stats(self, source: str) -> SourceStats:
        for s in self.sources:
            if s.source == source:
                return s
        s = SourceStats(source)
        self.sources.append(s)
        return s

    @property
    def total(self) -> SourceStats:
        return SourceStats(
            "total",
            sum(s.created for s in self.sources),
            sum(s.skipped for s in self.sources),
            sum(s.failed for s in self.sources),
        )

    def format(self) -> str:
        rows = [*self.sources, self.total]
        width = max([len("source"), *(len(r.source) for r in rows)])
        lines = ["Seed summary", f"{'source':<{width}}  {'created':>7}  {'skipped':>7}  {'failed':>6}"]
        lines += [f"{r.source:<{width}}  {r.created:>7}  {r.skipped:>7}  {r.failed:>6}" for r in rows]
        lines += [f"WARNING: {w}" for w in self.warnings]
        lines.append(f"elapsed: {self.elapsed_seconds:.1f} s")
        return "\n".join(lines)
