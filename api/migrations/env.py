"""Alembic environment. Online mode only, as the admin role; never falls back to DATABASE_URL."""

from __future__ import annotations

import logging
import sys

from alembic import context
from sqlalchemy import create_engine, pool

from investwatch_api.db.tables import metadata
from investwatch_api.logging_setup import setup_logging
from investwatch_api.settings import ConfigError, admin_database_url, log_level

config = context.config
if config.attributes.get("configure_logging", True) and not logging.getLogger().handlers:
    setup_logging(log_level())
log = logging.getLogger("investwatch_api.migrations")


def run_migrations_online() -> None:
    try:
        url = admin_database_url()
    except ConfigError as exc:
        log.error("migration aborted: %s", exc)
        raise
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=metadata, compare_server_default=False)
            with context.begin_transaction():
                context.run_migrations()
    except Exception as exc:
        # The URL (with its password) is never logged: only the error class and its message.
        log.error("migration failed: %s", type(exc).__name__)
        raise
    finally:
        engine.dispose()


if context.is_offline_mode():
    sys.exit("offline (--sql) mode is not supported; run against a database")
run_migrations_online()
