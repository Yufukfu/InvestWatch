"""Environment-only configuration (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# src/iw_mock_server/settings.py -> parents[3] is the contracts/ directory in a source checkout
_DEFAULT_CONTRACTS_DIR = Path(__file__).resolve().parents[3]
_DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _number(name: str, default: str, kind: type = float, minimum: float = 0):
    raw = _env(name, default)
    try:
        value = kind(raw)
    except ValueError:
        raise ValueError(f"{name} must be a {kind.__name__}, got {raw!r}") from None
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {raw!r}")
    return value


@dataclass(frozen=True)
class Settings:
    host: str = field(default_factory=lambda: _env("MOCK_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _number("MOCK_PORT", "8000", int, 1))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(o.strip() for o in _env("MOCK_CORS_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip())
    )
    replay_interval_s: float = field(default_factory=lambda: _number("MOCK_REPLAY_INTERVAL_S", "10"))
    scan_delay_s: float = field(default_factory=lambda: _number("MOCK_SCAN_DELAY_S", "2"))
    contracts_dir: Path = field(default_factory=lambda: Path(_env("CONTRACTS_DIR", str(_DEFAULT_CONTRACTS_DIR))))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))
