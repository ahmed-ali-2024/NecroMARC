"""Constant-time judge credential check (Req 7.3)."""
from __future__ import annotations

import hmac


def check_credentials(user, pw, cfg) -> bool:
    if not isinstance(user, str) or not isinstance(pw, str) or not user or not pw:
        return False
    u = user.encode("utf-8", "surrogatepass")
    p = pw.encode("utf-8", "surrogatepass")
    # Bitwise & (not `and`) so both comparisons always run.
    return bool(
        hmac.compare_digest(u, cfg.judge_username.encode("utf-8"))
        & hmac.compare_digest(p, cfg.judge_password.encode("utf-8"))
    )
