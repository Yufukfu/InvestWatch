"""JSON logs to stdout (integration-plan §7). URL credentials and SQL parameters are redacted from every line."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone

_EXTRA_KEYS = ("method", "path", "status", "event", "duration_ms", "reason")
# user:password@ in any URL, and the bound parameters SQLAlchemy appends to DBAPI errors (row data).
# Greedy up to the last "@" of the token, so an unencoded "/" or "@" in a password is still covered
# (at worst the host is masked too).
_URL_CREDENTIALS = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^\s@]*@", re.IGNORECASE)
_SQL_PARAMETERS = re.compile(r"\[parameters: .*?\](?=\s*(\(|\[|$))", re.DOTALL)


def redact(text: str) -> str:
    text = _URL_CREDENTIALS.sub(lambda m: m.group("scheme") + "***@", text)
    return _SQL_PARAMETERS.sub("[parameters: redacted]", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        for key in _EXTRA_KEYS:
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        if record.exc_info:
            entry["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(entry, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
