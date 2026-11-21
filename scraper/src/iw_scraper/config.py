import os
from pathlib import Path

# scraper/src/iw_scraper/config.py -> repository root is four levels up from this file
_REPO_ROOT = Path(__file__).resolve().parents[3]


def contracts_dir() -> Path:
    """Directory holding the JSON Schemas (`CONTRACTS_DIR`, default `<repo>/contracts`)."""
    override = os.environ.get("CONTRACTS_DIR")
    return Path(override) if override else _REPO_ROOT / "contracts"
