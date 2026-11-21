"""Every log line is one JSON object on stdout."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import TextIO

from iw_scraper.events import utc_iso

_HANDLER_MARK = "_iw_json_handler"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": utc_iso(datetime.fromtimestamp(record.created, UTC)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)  # newlines inside strings are escaped: one line per record


def configure_logging(stream: TextIO | None = None, level: int = logging.INFO) -> None:
    """Route the root logger (ours and third-party, such as arq) through the JSON formatter; idempotent."""
    root = logging.getLogger()
    for handler in [h for h in root.handlers if getattr(h, _HANDLER_MARK, False)]:
        root.removeHandler(handler)
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    setattr(handler, _HANDLER_MARK, True)
    root.addHandler(handler)
    root.setLevel(level)
