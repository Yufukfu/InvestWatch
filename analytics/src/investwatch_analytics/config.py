"""Settings from environment variables only (no paths into other repo folders)."""

from __future__ import annotations

import os
import socket
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

PIPELINE_VERSION = "0.1.0"
_DEFAULT_REGISTRY = Path(__file__).resolve().parents[2] / "registry" / "seed.csv"


@dataclass(frozen=True)
class Settings:
    registry_csv: Path
    log_level: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        return cls(
            registry_csv=Path(env.get("REGISTRY_CSV") or _DEFAULT_REGISTRY),
            log_level=(env.get("LOG_LEVEL") or "INFO").upper(),
        )


def uses_seed_registry(settings: Settings) -> bool:
    """True when the registry is the bundled fictional `registry/seed.csv` (3 `*.example.com` firms): R1 results
    and high-risk alerts for real firms are then not meaningful until `REGISTRY_CSV` names a real KNF registry."""
    return settings.registry_csv.resolve() == _DEFAULT_REGISTRY.resolve()



class ConfigError(ValueError):
    """A missing or malformed environment variable; the message names it."""


def _required(env: Mapping[str, str], key: str) -> str:
    value = (env.get(key) or "").strip()
    if not value:
        raise ConfigError(f"{key} is required for the worker")
    return value


def _positive_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{key} must be an integer, got {raw!r}") from None
    if value < 1:
        raise ConfigError(f"{key} must be at least 1, got {value}")
    return value


@dataclass(frozen=True)
class WorkerSettings:
    """Settings the stream worker needs on top of `Settings`; the CLI does not need them."""

    database_url: str
    redis_url: str
    consumer: str
    stream_block_ms: int
    claim_min_idle_ms: int
    max_deliveries: int
    health_port: int
    max_document_bytes: int

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "WorkerSettings":
        env = os.environ if env is None else env
        return cls(
            database_url=_required(env, "DATABASE_URL"),
            redis_url=_required(env, "REDIS_URL"),
            consumer=(env.get("WORKER_CONSUMER") or "").strip() or socket.gethostname(),
            stream_block_ms=_positive_int(env, "STREAM_BLOCK_MS", 5000),
            claim_min_idle_ms=_positive_int(env, "CLAIM_MIN_IDLE_MS", 60000),
            max_deliveries=_positive_int(env, "MAX_DELIVERIES", 5),
            health_port=_positive_int(env, "HEALTH_PORT", 8001),
            max_document_bytes=_positive_int(env, "MAX_DOCUMENT_BYTES", 2_000_000),
        )
