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
