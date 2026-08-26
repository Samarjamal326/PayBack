from __future__ import annotations

import logging
import re
import sys
from typing import Any

# Filter pattern to mask sensitive keys/tokens from logs
SECRET_PATTERNS = [
    re.compile(r"(rzp_live_[a-zA-Z0-9]+)"),
    re.compile(r"(rzp_test_[a-zA-Z0-9]+)"),
    re.compile(r"(Bearer\s+[a-zA-Z0-9_\-\.]+)"),
    re.compile(r"('password':\s*')[^']+(')"),
    re.compile(r"('key_secret':\s*')[^']+(')"),
]


class SensitiveDataFilter(logging.Filter):
    """Redacts secrets and auth tokens from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pat in SECRET_PATTERNS:
                record.msg = pat.sub("[REDACTED]", record.msg)
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Configures structured, sanitized logging for PayBack."""
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    # Replace existing handlers
    root_logger.handlers = [handler]
