"""Shared fixtures. Contract-backed tests need CONTRACTS_DIR (e.g. ../contracts) and are skipped without it."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

NOW = datetime(2026, 11, 21, 16, 0, tzinfo=timezone.utc)


def pg_test_url() -> str | None:
    """Throwaway Postgres for the store tests: `TEST_DATABASE_URL`, else CI's `TEST_DATABASE_ADMIN_URL` (#24).
    Never `DATABASE_URL`, which may point at a real stack. The role must be allowed to CREATE DATABASE."""
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get("TEST_DATABASE_ADMIN_URL") or None


def redis_test_url() -> str | None:
    """Throwaway Redis for the real-Redis test: `TEST_REDIS_URL`, else CI's `IW_TEST_REDIS_URL` (#24), never
    `REDIS_URL`."""
    return os.environ.get("TEST_REDIS_URL") or os.environ.get("IW_TEST_REDIS_URL") or None


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


# ---- LLM test doubles (analytics-llm-p0): tests never call a real LLM ----------------------------


@pytest.fixture
def stub_llm():
    from llm_stub import StubLLM

    stub = StubLLM()
    try:
        yield stub
    finally:
        stub.stop()


@pytest.fixture(autouse=True)
def _no_real_llm(monkeypatch):
    """Fail any test whose HTTP request leaves the loopback host (a real LLM endpoint by accident)."""
    try:
        import httpx
    except ImportError:  # pragma: no cover - httpx is a runtime dependency
        return
    original = httpx.Client.send

    def guarded(self, request, *args, **kwargs):
        if request.url.host not in ("127.0.0.1", "localhost", "::1"):
            raise AssertionError(f"test tried to reach a non-local host: {request.url.host}")
        return original(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "send", guarded)
