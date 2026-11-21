"""Shared fixtures. Contract-backed tests need CONTRACTS_DIR (e.g. ../contracts) and are skipped without it."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

NOW = datetime(2026, 11, 21, 16, 0, tzinfo=timezone.utc)


def _contracts_dir() -> Path | None:
    value = os.environ.get("CONTRACTS_DIR")
    return Path(value) if value else None


@pytest.fixture
def contracts_dir() -> Path:
    path = _contracts_dir()
    if path is None:
        pytest.skip("CONTRACTS_DIR not set")
    return path


@pytest.fixture
def mock_documents(contracts_dir: Path) -> list[dict]:
    return json.loads((contracts_dir / "mocks" / "documents.json").read_text(encoding="utf-8"))


@pytest.fixture
def finding_validator(contracts_dir: Path):
    from jsonschema import Draft202012Validator, FormatChecker

    schema = json.loads((contracts_dir / "schemas" / "finding.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def make_doc(**overrides) -> dict:
    """Minimal valid ScrapedDocument v1 as a dict."""
    doc = {
        "id": "11111111-1111-4111-8111-111111111111",
        "platform": "web",
        "source_kind": "firm_own",
        "url": "https://example.com/oferta",
        "fetched_at": "2026-11-21T12:00:00Z",
        "text": "Reklama. Przykładowy tekst.",
    }
    doc.update(overrides)
    return doc
