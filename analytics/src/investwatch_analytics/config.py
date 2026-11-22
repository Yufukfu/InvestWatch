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
#: The LLM client's connect timeout (llm/client.py CONNECT_TIMEOUT_S): the budget check leaves room for it.
CONNECT_MARGIN_S = 3.0


def _check_base_url(url: str, *, has_key: bool) -> None:
    """http(s) with a host, no credentials, query or fragment; a key never goes over plain http to a remote host.

    The message never quotes the URL: it could carry a password or a key in the query.
    """
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in url):
        raise ConfigError("LLM_BASE_URL must not contain whitespace or control characters")
    try:
        parts = urlsplit(url)
        host = parts.hostname
        userinfo = parts.username is not None or parts.password is not None
        parts.port  # noqa: B018 - urlsplit validates the port only when it is read
    except ValueError:
        raise ConfigError("LLM_BASE_URL is not a valid URL (check the host and port)") from None
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
        # The budget is checked between requests, so one request (connect + read) can overrun it: keep that margin.
        if claim_min_idle_ms is not None and (s.doc_budget_s + CONNECT_MARGIN_S) * 1000 >= claim_min_idle_ms:
            # Otherwise a second consumer XAUTOCLAIMs a message still being judged (ADR 0310).
            raise ConfigError(
                f"LLM_DOC_BUDGET_S ({s.doc_budget_s:g} s) plus {CONNECT_MARGIN_S:g} s must be below "
                f"CLAIM_MIN_IDLE_MS ({claim_min_idle_ms} ms)"
            )
        return s


# ---- Embeddings, topic gate, near-dup (analytics-embeddings; ADR 0313, 0314) ----------------------
# A separate block so it merges cleanly with the LLM settings above.


def _check_url(url: str, var: str, *, has_key: bool, key_var: str) -> None:
    """Same rules as `_check_base_url`, naming `var`; the message never quotes the URL (it may carry secrets)."""
    try:
        parts = urlsplit(url)
        host = parts.hostname
        userinfo = parts.username is not None or parts.password is not None
        parts.port  # urlsplit checks the port only when it is read
    except ValueError:
        raise ConfigError(f"{var} is not a valid URL") from None
    if any(c.isspace() for c in url):
        raise ConfigError(f"{var} must not contain whitespace")
    if parts.scheme not in ("http", "https") or not host:
        raise ConfigError(f"{var} must be an http(s) URL with a host, e.g. http://ollama:11434/v1")
    if userinfo or parts.query or parts.fragment:
        raise ConfigError(f"{var} must not carry credentials, a query or a fragment (put the key in {key_var})")
    if has_key and parts.scheme == "http" and host not in _LOCAL_HOSTS:
        raise ConfigError(f"{var} must use https when {key_var} is set and the host is not local")


def _unit_interval(env: Mapping[str, str], key: str, default: float) -> float:
    """A number in (0, 1]."""
    value = _positive_number(env, key, default)
    if value > 1:
        raise ConfigError(f"{key} must be in (0, 1], got {env.get(key)!r}")
    return value


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _flag(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = (env.get(key) or "").strip().lower()
    if not raw:
        return default
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ConfigError(f"{key} must be true or false, got {env.get(key)!r}")


@dataclass(frozen=True)
class EmbedSettings:
    """OpenAI-compatible `/embeddings` endpoint, env only, local by default (ADR 0313). Empty URL = disabled."""

    base_url: str = ""
    model: str = "bge-m3"
    api_key: str = field(default="", repr=False)  # never in a repr, log or error message
    dim: int = 1024
    timeout_s: float = 15  # warm bge-m3 on a loaded CPU: 4-12 s per document (task 9.4)
    max_chars: int = 4000
    cache_ttl_s: int = 604800
    breaker_failures: int = 3
    breaker_cooldown_s: float = 60

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    @property
    def mode(self) -> str:
        """`local` (Ollama / loopback), `remote`, or `disabled`; logged at worker start."""
        if not self.enabled:
            return "disabled"
        return "local" if (urlsplit(self.base_url).hostname or "") in _LOCAL_HOSTS else "remote"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, *, claim_min_idle_ms: int | None = None,
                 llm_doc_budget_s: float = 0) -> "EmbedSettings":
        env = os.environ if env is None else env
        base_url = (env.get("EMBED_BASE_URL") or "").strip()
        if not base_url:
            return cls()
        api_key = (env.get("EMBED_API_KEY") or "").strip()
        _check_url(base_url, "EMBED_BASE_URL", has_key=bool(api_key), key_var="EMBED_API_KEY")
        raw_model = env.get("EMBED_MODEL")
        model = "bge-m3" if raw_model is None else raw_model.strip()
        if not model:
            raise ConfigError("EMBED_MODEL must not be empty when EMBED_BASE_URL is set")
        s = cls(
            base_url=base_url,
            model=model,
            api_key=api_key,
            dim=int(_positive_number(env, "EMBED_DIM", 1024, integer=True)),
            timeout_s=_positive_number(env, "EMBED_TIMEOUT_S", 15),
            max_chars=int(_positive_number(env, "EMBED_MAX_CHARS", 4000, integer=True)),
            cache_ttl_s=int(_positive_number(env, "EMBED_CACHE_TTL_S", 604800, integer=True)),
            breaker_failures=int(_positive_number(env, "EMBED_BREAKER_FAILURES", 3, integer=True)),
            breaker_cooldown_s=_positive_number(env, "EMBED_BREAKER_COOLDOWN_S", 60),
        )
        if claim_min_idle_ms is not None and (llm_doc_budget_s + s.timeout_s) * 1000 >= claim_min_idle_ms:
            # The embedding call adds to the LLM budget; both must end before XAUTOCLAIM (ADR 0310).
            raise ConfigError(
                f"LLM_DOC_BUDGET_S + EMBED_TIMEOUT_S ({llm_doc_budget_s + s.timeout_s:g} s) must be below "
                f"CLAIM_MIN_IDLE_MS ({claim_min_idle_ms} ms)"
            )
        return s


@dataclass(frozen=True)
class GateSettings:
    """Investment topic gate (ADR 0314). `sim_threshold` is used only by the stretch similarity rescue."""

    enabled: bool = True
    sim_threshold: float = 0.45

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "GateSettings":
        env = os.environ if env is None else env
        return cls(enabled=_flag(env, "GATE_ENABLED", True),
                   sim_threshold=_unit_interval(env, "GATE_SIM_THRESHOLD", 0.45))


@dataclass(frozen=True)
class NearDupSettings:
    """MinHash near-dup index in Redis (ADR 0314): `num_perm` = `bands` x `rows`."""

    num_perm: int = 128
    bands: int = 32
    threshold: float = 0.8
    max_chars: int = 50000
    ttl_s: int = 2592000

    @property
    def rows(self) -> int:
        return self.num_perm // self.bands

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "NearDupSettings":
        env = os.environ if env is None else env
        num_perm = int(_positive_number(env, "NEARDUP_NUM_PERM", 128, integer=True))
        bands = int(_positive_number(env, "NEARDUP_BANDS", 32, integer=True))
        if num_perm % bands:  # also rejects bands > num_perm
            raise ConfigError(f"NEARDUP_BANDS ({bands}) must divide NEARDUP_NUM_PERM ({num_perm})")
        return cls(
            num_perm=num_perm,
            bands=bands,
            threshold=_unit_interval(env, "NEARDUP_THRESHOLD", 0.8),
            max_chars=int(_positive_number(env, "NEARDUP_MAX_CHARS", 50000, integer=True)),
            ttl_s=int(_positive_number(env, "NEARDUP_TTL_S", 2592000, integer=True)),
        )
