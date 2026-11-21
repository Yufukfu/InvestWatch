"""Settings from environment variables only (no paths into other repo folders)."""

from __future__ import annotations

import json
import math
import os
import socket
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

PIPELINE_VERSION = "0.1.0"
_REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry"
#: The fictional 3-firm fixture whose ids match contracts/mocks; tests name it explicitly.
SEED_REGISTRY = _REGISTRY_DIR / "seed.csv"
#: The real KNF register, a snapshot written by `python -m investwatch_analytics.knf` (ADR 0311).
KNF_REGISTRY = _REGISTRY_DIR / "knf.csv"
_DEFAULT_REGISTRY = KNF_REGISTRY


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
    """True when the registry is the bundled fictional `registry/seed.csv` (4 fictional `*.example.com` firms): R1 results
    and high-risk alerts for real firms are then not meaningful."""
    return settings.registry_csv.resolve() == SEED_REGISTRY.resolve()


def registry_provenance(registry_csv: Path) -> dict | None:
    """The `<name>.meta.json` written next to a loader-made registry (`fetched_at`, counts), or None when it is
    missing or unreadable: a hand-made registry."""
    path = registry_csv.with_name(registry_csv.stem + ".meta.json")
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return meta if isinstance(meta, dict) else None



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


# ---- LLM (analytics-llm-p0; ADR 0304, 0309, 0310) -------------------------------------------------


def _positive_number(env: Mapping[str, str], key: str, default: float, *, integer: bool = False) -> float:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw) if integer else float(raw)
    except ValueError:
        kind = "an integer" if integer else "a number"
        raise ConfigError(f"{key} must be {kind}, got {raw!r}") from None
    if not math.isfinite(value) or value <= 0:
        raise ConfigError(f"{key} must be a positive finite number, got {raw!r}")
    return value


_LOCAL_HOSTS = {"ollama", "localhost", "127.0.0.1", "::1"}


def _check_base_url(url: str, *, has_key: bool) -> None:
    """http(s) with a host, no credentials, query or fragment; a key never goes over plain http to a remote host.

    The message never quotes the URL: it could carry a password or a key in the query.
    """
    try:
        parts = urlsplit(url)
        host = parts.hostname
        userinfo = parts.username is not None or parts.password is not None
    except ValueError:
        raise ConfigError("LLM_BASE_URL is not a valid URL") from None
    if parts.scheme not in ("http", "https") or not host:
        raise ConfigError("LLM_BASE_URL must be an http(s) URL with a host, e.g. http://ollama:11434/v1")
    if userinfo or parts.query or parts.fragment:
        raise ConfigError("LLM_BASE_URL must not carry credentials, a query or a fragment (put the key in LLM_API_KEY)")
    if has_key and parts.scheme == "http" and host not in _LOCAL_HOSTS:
        raise ConfigError("LLM_BASE_URL must use https when LLM_API_KEY is set and the host is not local")


@dataclass(frozen=True)
class LlmSettings:
    """OpenAI-compatible chat completions endpoint, env only. Empty `LLM_BASE_URL` = disabled (rules-only)."""

    base_url: str = ""
    model: str = ""
    api_key: str = field(default="", repr=False)  # never in a repr, log or error message
    timeout_s: float = 20
    doc_budget_s: float = 40
    chunk_chars: int = 9000
    max_chunks: int = 4
    cache_ttl_s: int = 604800
    breaker_failures: int = 3
    breaker_cooldown_s: float = 60

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    @property
    def mode(self) -> str:
        """`local` (Ollama / loopback), `hosted`, or `disabled`; logged at worker start."""
        if not self.enabled:
            return "disabled"
        return "local" if (urlsplit(self.base_url).hostname or "") in _LOCAL_HOSTS else "hosted"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, *, claim_min_idle_ms: int | None = None) -> "LlmSettings":
        env = os.environ if env is None else env
        base_url = (env.get("LLM_BASE_URL") or "").strip()
        if not base_url:
            return cls()
        _check_base_url(base_url, has_key=bool((env.get("LLM_API_KEY") or "").strip()))
        model = (env.get("LLM_MODEL") or "").strip()
        if not model:
            raise ConfigError("LLM_MODEL is required when LLM_BASE_URL is set")
        s = cls(
            base_url=base_url,
            model=model,
            api_key=(env.get("LLM_API_KEY") or "").strip(),
            timeout_s=_positive_number(env, "LLM_TIMEOUT_S", 20),
            doc_budget_s=_positive_number(env, "LLM_DOC_BUDGET_S", 40),
            chunk_chars=int(_positive_number(env, "LLM_CHUNK_CHARS", 9000, integer=True)),
            max_chunks=int(_positive_number(env, "LLM_MAX_CHUNKS", 4, integer=True)),
            cache_ttl_s=int(_positive_number(env, "LLM_CACHE_TTL_S", 604800, integer=True)),
            breaker_failures=int(_positive_number(env, "LLM_BREAKER_FAILURES", 3, integer=True)),
            breaker_cooldown_s=_positive_number(env, "LLM_BREAKER_COOLDOWN_S", 60),
        )
        if claim_min_idle_ms is not None and s.doc_budget_s * 1000 >= claim_min_idle_ms:
            # Otherwise a second consumer XAUTOCLAIMs a message still being judged (ADR 0310).
            raise ConfigError(
                f"LLM_DOC_BUDGET_S ({s.doc_budget_s:g} s) must be below CLAIM_MIN_IDLE_MS ({claim_min_idle_ms} ms)"
            )
        return s
