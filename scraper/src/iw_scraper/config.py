import os
from dataclasses import fields
from pathlib import Path

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
