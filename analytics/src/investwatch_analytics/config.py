"""Settings from environment variables only (no paths into other repo folders)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PIPELINE_VERSION = "0.1.0"
_DEFAULT_REGISTRY = Path(__file__).resolve().parents[2] / "registry" / "seed.csv"


@dataclass(frozen=True)
class Settings:
    registry_csv: Path
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            registry_csv=Path(os.environ.get("REGISTRY_CSV") or _DEFAULT_REGISTRY),
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        )
