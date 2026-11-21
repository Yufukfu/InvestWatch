"""Where failures go: credential redaction, the job error sink and the JSON logger."""

import json
import logging
import re
import sys
import traceback
from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol, TextIO

from iw_scraper.types import JobError

# `user:pass@` between `://` and the next `/` or whitespace; greedy, so an `@` in the password is covered
_URL_CREDENTIALS = re.compile(r"(?<=://)[^/\s]*@")
_REDACTED = "***@"

# attributes every LogRecord has; anything else came from `extra=`
_RECORD_ATTRIBUTES = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


def redact(text: str) -> str:
    """Replace `user:pass@` in every URL of `text`, so no proxy credentials reach a log or an error."""
    return _URL_CREDENTIALS.sub(_REDACTED, text)


class JobErrorSink(Protocol):
    """Where a final job error is recorded (the database sink arrives with `scraper-ingest`)."""

    def record(self, error: JobError) -> None: ...


class InMemorySink:
    def __init__(self) -> None:
        self.errors: list[JobError] = []

    def record(self, error: JobError) -> None:
        self.errors.append(replace(error, detail=redact(error.detail)))


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RECORD_ATTRIBUTES:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = "".join(traceback.format_exception(*record.exc_info))
        # one redaction pass over the finished line also covers nested values
        return redact(json.dumps(payload, default=str, ensure_ascii=False))


def json_logger(name: str, stream: TextIO | None = None) -> logging.Logger:
    """A logger that writes one redacted JSON object per line (stdout by default). Safe to call twice."""
    logger = logging.getLogger(name)
    for handler in list(logger.handlers):
        if isinstance(handler.formatter, _JsonFormatter):
            logger.removeHandler(handler)
    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
