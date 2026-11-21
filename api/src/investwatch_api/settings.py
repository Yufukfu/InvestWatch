"""Environment-only configuration (integration-plan §7). Values are never logged."""

from __future__ import annotations

import os
from pathlib import Path

_SCHEMES = ("postgresql+psycopg://", "postgresql://", "postgres://")
# src/investwatch_api/settings.py -> parents[3] is the repository root in a source checkout
_DEFAULT_CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"


class ConfigError(RuntimeError):
    """A required environment variable is missing or malformed. The message names the variable only."""


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set")
    return value


def _psycopg_url(name: str) -> str:
    """Normalise a Postgres URL to the psycopg 3 dialect (ADR 0307)."""
    raw = _required(name)
    for scheme in _SCHEMES:
        if raw.startswith(scheme):
            return "postgresql+psycopg://" + raw[len(scheme):]
    raise ConfigError(f"{name} must be a postgresql:// URL")


def admin_database_url() -> str:
    """URL of the admin role (iw_admin). Only Alembic uses it; never falls back to DATABASE_URL."""
    return _psycopg_url("DATABASE_ADMIN_URL")


def app_database_url() -> str:
    """URL of the application role (iw_app): CRUD, no DDL."""
    return _psycopg_url("DATABASE_URL")


def contracts_dir() -> Path:
    value = os.environ.get("CONTRACTS_DIR", "").strip()
    return Path(value) if value else _DEFAULT_CONTRACTS_DIR


def log_level() -> str:
    return os.environ.get("LOG_LEVEL", "").strip().upper() or "INFO"


def redis_url() -> str:
    raw = _required("REDIS_URL")
    if not raw.startswith(("redis://", "rediss://")):
        raise ConfigError("REDIS_URL must be a redis:// URL")
    return raw


def cors_origins() -> tuple[str, ...]:
    """Origins allowed besides the same origin (the gateway case); empty by default."""
    raw = os.environ.get("CORS_ORIGINS", "")
    return tuple(o.strip() for o in raw.split(",") if o.strip())


def minio_settings() -> dict:
    return {
        "endpoint": _required("MINIO_ENDPOINT"),
        "access_key": _required("MINIO_ACCESS_KEY"),
        "secret_key": _required("MINIO_SECRET_KEY"),
        "bucket": os.environ.get("MINIO_BUCKET", "").strip() or "iw-raw",
        "secure": os.environ.get("MINIO_SECURE", "").strip().lower() in ("1", "true", "yes"),
    }
