import math
import os
from dataclasses import dataclass, fields
from pathlib import Path
from urllib.parse import urlsplit

from iw_scraper.ratelimit import host_key

# scraper/src/iw_scraper/config.py -> repository root is four levels up from this file
_REPO_ROOT = Path(__file__).resolve().parents[3]


def contracts_dir() -> Path:
    """Directory holding the JSON Schemas (`CONTRACTS_DIR`, default `<repo>/contracts`)."""
    override = os.environ.get("CONTRACTS_DIR")
    return Path(override) if override else _REPO_ROOT / "contracts"


def from_env(cls, *, prefix: str = "SCRAPER_", **fixed):
    """Build a settings dataclass from `SCRAPER_<FIELD>` variables; unset ones keep the dataclass default."""
    values = dict(fixed)
    for field in fields(cls):
        name = prefix + field.name.upper()
        if field.name in values or name not in os.environ:
            continue
        kind = type(field.default)
        try:
            values[field.name] = kind(os.environ[name])
        except ValueError as error:
            raise ValueError(f"{name} must be a {kind.__name__}") from error  # never echo the value
    return cls(**values)


DEFAULT_PROXY_COOLDOWN_SECONDS = 90.0
_ROTATION_MODES = ("per_request", "per_session")
_PROXY_SCHEMES = ("http", "https", "socks5")


def proxy_settings() -> tuple[list[str], str, float]:
    """(`PROXY_LIST`, `PROXY_ROTATION`, `PROXY_COOLDOWN_SECONDS`). The list may hold credentials: never log it."""
    proxies = [item.strip() for item in os.environ.get("PROXY_LIST", "").split(",") if item.strip()]
    for position, entry in enumerate(proxies, start=1):  # never echo an entry: it may hold credentials
        parts = urlsplit(entry)
        if parts.scheme not in _PROXY_SCHEMES or not parts.hostname:
            raise ValueError(f"PROXY_LIST entry {position} is not a http, https or socks5 proxy URL")
    mode = os.environ.get("PROXY_ROTATION", "per_request")
    if mode not in _ROTATION_MODES:
        raise ValueError(f"PROXY_ROTATION must be one of {_ROTATION_MODES}")
    cooldown = float(os.environ.get("PROXY_COOLDOWN_SECONDS", DEFAULT_PROXY_COOLDOWN_SECONDS))
    if not math.isfinite(cooldown) or cooldown <= 0:
        raise ValueError("PROXY_COOLDOWN_SECONDS must be a positive number")
    return proxies, mode, cooldown


DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_DOMAIN_MIN_INTERVAL_SECONDS = 5.0


def _positive_number(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return value


def rate_limit_settings() -> tuple[str, float]:
    """(`REDIS_URL`, `DOMAIN_MIN_INTERVAL_SECONDS`). The URL may hold a password: never log it."""
    url = os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)
    return url, _positive_number("DOMAIN_MIN_INTERVAL_SECONDS", DEFAULT_DOMAIN_MIN_INTERVAL_SECONDS)



DEFAULT_ALLOWED_PORTS = (80, 443)


def _host_list(name: str, *, strip_www: bool) -> frozenset[str]:
    hosts = (item.strip().lower() for item in os.environ.get(name, "").split(","))
    return frozenset(host_key(h) if strip_www else h for h in hosts if h)


def _ports() -> tuple[int, ...]:
    raw = os.environ.get("ALLOWED_PORTS")
    if raw is None:
        return DEFAULT_ALLOWED_PORTS
    try:
        ports = [int(item) for item in raw.split(",") if item.strip()]
    except ValueError:
        ports = []
    if not ports or not all(0 < port < 65536 for port in ports):
        raise ValueError("ALLOWED_PORTS must be a comma-separated list of ports between 1 and 65535")
    return tuple(dict.fromkeys(ports))


def target_settings() -> tuple[tuple[int, ...], frozenset[str], frozenset[str]]:
    """(`ALLOWED_PORTS`, `COMPOSE_INTERNAL_HOSTS`, `FETCH_EXTRA_HOSTS`): what the target guards enforce."""
    return (
        _ports(),
        _host_list("COMPOSE_INTERNAL_HOSTS", strip_www=False),
        _host_list("FETCH_EXTRA_HOSTS", strip_www=True),
    )


DEFAULT_FETCH_TIMEOUT_SECONDS = 20.0
DEFAULT_FETCH_MAX_BYTES = 5 * 1024 * 1024


def fetch_settings() -> tuple[float, int]:
    """(`FETCH_TIMEOUT_SECONDS`, `FETCH_MAX_BYTES`): the per-request timeout and the response size cap."""
    timeout = _positive_number("FETCH_TIMEOUT_SECONDS", DEFAULT_FETCH_TIMEOUT_SECONDS)
    try:
        max_bytes = int(os.environ.get("FETCH_MAX_BYTES", DEFAULT_FETCH_MAX_BYTES))
    except ValueError:
        max_bytes = 0
    if max_bytes < 1:
        raise ValueError("FETCH_MAX_BYTES must be a whole number of bytes, at least 1")
    return timeout, max_bytes


DEFAULT_RENDERER_URL = "http://renderer:8080"
DEFAULT_RENDER_MAX_PER_HOUR = 20
DEFAULT_RENDER_TIMEOUT_SECONDS = 90.0
ATTEMPT_ROOM_SECONDS = 60.0  # what the rest of a run (robots, fetch, politeness delays, ingest) may take next to a render
_TRUE, _FALSE = ("true", "1", "yes"), ("false", "0", "no", "")


@dataclass(frozen=True)
class RenderSettings:
    enabled: bool
    max_per_hour: int
    url: str
    timeout_seconds: float


def render_settings(*, attempt_timeout: float) -> RenderSettings:
    """The render step's switches (`SCRAPER_RENDER_ENABLED`, `SCRAPER_RENDER_MAX_PER_HOUR`, `RENDERER_URL`,
    `RENDER_TIMEOUT_SECONDS`). With the step enabled the attempt must outlast a render, or the job's own timeout
    would cut it off and the document with it."""
    raw = os.environ.get("SCRAPER_RENDER_ENABLED", "false").strip().lower()  # `bool("false")` is True: parse it by hand
    if raw not in _TRUE + _FALSE:
        raise ValueError("SCRAPER_RENDER_ENABLED must be true or false")
    try:
        max_per_hour = int(os.environ.get("SCRAPER_RENDER_MAX_PER_HOUR", DEFAULT_RENDER_MAX_PER_HOUR))
    except ValueError:
        max_per_hour = -1
    if max_per_hour < 0:
        raise ValueError("SCRAPER_RENDER_MAX_PER_HOUR must be a whole number, 0 or more")
    url = os.environ.get("RENDERER_URL", DEFAULT_RENDERER_URL).rstrip("/")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("RENDERER_URL must be an http or https URL")
    timeout = _positive_number("RENDER_TIMEOUT_SECONDS", DEFAULT_RENDER_TIMEOUT_SECONDS)
    enabled = raw in _TRUE
    if enabled and attempt_timeout < timeout + ATTEMPT_ROOM_SECONDS:
        raise ValueError(
            f"SCRAPER_ATTEMPT_TIMEOUT ({attempt_timeout:g}) must be at least RENDER_TIMEOUT_SECONDS "
            f"({timeout:g}) plus {ATTEMPT_ROOM_SECONDS:g} seconds while SCRAPER_RENDER_ENABLED is true"
        )
    return RenderSettings(enabled, max_per_hour, url, timeout)
