from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

CONTRACTS_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def contracts_dir() -> Path:
    return CONTRACTS_DIR


@pytest.fixture
def contracts_copy(tmp_path: Path) -> Path:
    """A writable copy of schemas/ and mocks/ for tests that corrupt data."""
    dst = tmp_path / "contracts"
    shutil.copytree(CONTRACTS_DIR / "schemas", dst / "schemas")
    shutil.copytree(CONTRACTS_DIR / "mocks", dst / "mocks")
    shutil.copy(CONTRACTS_DIR / "openapi.yaml", dst / "openapi.yaml")
    return dst


def schema_validator(name: str) -> Draft202012Validator:
    schema = json.loads((CONTRACTS_DIR / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def assert_valid(name: str, instance) -> None:
    errors = [f"{'/'.join(map(str, e.path))}: {e.message}" for e in schema_validator(name).iter_errors(instance)]
    assert not errors, f"{name} schema violations: {errors}"
