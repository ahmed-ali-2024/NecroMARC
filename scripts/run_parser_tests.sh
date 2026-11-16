#!/usr/bin/env bash
# Run the parser test suite (used by the Kiro PostFileSave hook).
# Combined output goes to stderr and .kiro/hooks/last-run.log; exits with pytest's status.
set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3 || command -v python)"
fi

LOG="$ROOT/.kiro/hooks/last-run.log"
mkdir -p "$(dirname "$LOG")"

HYPOTHESIS_PROFILE="${HYPOTHESIS_PROFILE:-ci}" "$PY" -m pytest backend/parser 2>&1 | tee "$LOG" >&2
exit "${PIPESTATUS[0]}"
