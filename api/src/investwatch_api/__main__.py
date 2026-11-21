"""python -m investwatch_api: serve the API and Socket.IO on API_HOST:API_PORT (default 0.0.0.0:8000)."""

from __future__ import annotations

import asyncio
import os
import sys

import uvicorn

from .app import create_asgi
from .logging_setup import setup_logging
from .settings import log_level


def main() -> None:
    setup_logging(log_level())
    if sys.platform == "win32":  # psycopg async cannot use the Proactor loop; containers run Linux
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(create_asgi(), host=os.environ.get("API_HOST", "0.0.0.0"), port=int(os.environ.get("API_PORT", "8000")),
                proxy_headers=True, forwarded_allow_ips="*", log_config=None,
                loop="none" if sys.platform == "win32" else "auto")


if __name__ == "__main__":
    main()
