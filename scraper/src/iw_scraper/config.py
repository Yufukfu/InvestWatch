import math
import os
from pathlib import Path
from urllib.parse import urlsplit

# scraper/src/iw_scraper/config.py -> repository root is four levels up from this file
_REPO_ROOT = Path(__file__).resolve().parents[3]


def contracts_dir() -> Path:
    """Directory holding the JSON Schemas (`CONTRACTS_DIR`, default `<repo>/contracts`)."""
    override = os.environ.get("CONTRACTS_DIR")
    return Path(override) if override else _REPO_ROOT / "contracts"


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
DEFAULT_MAX_RETRY_AFTER_SECONDS = 300.0
DEFAULT_DOMAIN_FAILURE_THRESHOLD = 5
DEFAULT_DOMAIN_PAUSE_SECONDS = 600.0


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


def domain_gate_settings() -> tuple[float, int, float]:
    """(`MAX_RETRY_AFTER_SECONDS`, `DOMAIN_FAILURE_THRESHOLD`, `DOMAIN_PAUSE_SECONDS`)."""
    try:
        threshold = int(os.environ.get("DOMAIN_FAILURE_THRESHOLD", DEFAULT_DOMAIN_FAILURE_THRESHOLD))
    except ValueError:
        threshold = 0
    if threshold < 1:
        raise ValueError("DOMAIN_FAILURE_THRESHOLD must be a whole number of at least 1")
    return (
        _positive_number("MAX_RETRY_AFTER_SECONDS", DEFAULT_MAX_RETRY_AFTER_SECONDS),
        threshold,
        _positive_number("DOMAIN_PAUSE_SECONDS", DEFAULT_DOMAIN_PAUSE_SECONDS),
    )
