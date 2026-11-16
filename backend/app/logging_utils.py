"""Log filter that masks configured secret values."""
from __future__ import annotations

import logging
import traceback
from typing import Iterable

REDACTED = "[REDACTED]"


class SecretRedactingFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str] = ()):
        super().__init__()
        # Longest first so a secret containing another is fully masked.
        self._secrets = sorted({s for s in secrets if s}, key=len, reverse=True)

    def redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, REDACTED)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        record.msg = self.redact(message)
        record.args = None
        if record.exc_info and record.exc_info[0] is not None:
            text = "".join(traceback.format_exception(*record.exc_info))
            record.exc_text = self.redact(text)
        elif record.exc_text:
            record.exc_text = self.redact(record.exc_text)
        if record.stack_info:
            record.stack_info = self.redact(record.stack_info)
        return True


def install_redaction(secrets: Iterable[str]) -> SecretRedactingFilter:
    """Attach the filter to the root logger and its current handlers."""
    flt = SecretRedactingFilter(secrets)
    root = logging.getLogger()
    root.addFilter(flt)
    # Records from child loggers skip root logger filters, so attach to handlers too.
    for handler in root.handlers:
        handler.addFilter(flt)
    return flt
