"""Entry point: `python -m iw_mock_server` (configuration from environment variables)."""

from __future__ import annotations

import logging
import sys

import uvicorn

from .events import create_asgi_app
from .logging_setup import setup_logging
from .settings import Settings
from .store import MockDataError, Store, load_mock_data

log = logging.getLogger("iw_mock_server")


def main() -> int:
    try:
        settings = Settings()
    except ValueError as exc:
        setup_logging()
        log.error("invalid configuration: %s", exc)
        return 2
    setup_logging(settings.log_level)

    try:
        store = Store(load_mock_data(settings.contracts_dir))
    except MockDataError as exc:
        log.error("cannot start, mock data is invalid: %s", exc)
        return 1

    log.info("mock server on http://%s:%s/api (Socket.IO namespace /events, replay every %ss)",
             settings.host, settings.port, settings.replay_interval_s)
    # log_config=None keeps uvicorn on the root JSON handler instead of its own formatters
    uvicorn.run(create_asgi_app(settings, store), host=settings.host, port=settings.port, log_config=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
