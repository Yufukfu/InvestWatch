"""Load and validate contracts/mocks, keep an in-memory copy the API can change."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

MODULES = ("M1", "M2", "M3")
MEDIUM_BAND = 0.2  # medium = within 0.2 below the threshold (integration-plan §4)


class MockDataError(RuntimeError):
    """A mock file is missing, unreadable or does not match its schema."""


@dataclass(frozen=True)
class MockData:
    findings: list[dict]
    documents: list[dict]
    sources: list[dict]
    events: list[dict]
    trend: dict
    calibration: dict[str, dict]
    thresholds: dict[str, float]
    health: dict


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MockDataError(f"missing mock file: {path.name} ({path})") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise MockDataError(f"cannot read {path.name}: {exc}") from exc


def _validator(contracts_dir: Path, schema_file: str) -> Draft202012Validator:
    schema = _read_json(contracts_dir / "schemas" / schema_file)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate_items(items, validator: Draft202012Validator, file_name: str) -> list[dict]:
    if not isinstance(items, list):
        raise MockDataError(f"{file_name}: expected a list of items")
    for index, item in enumerate(items):
        error = next(iter(validator.iter_errors(item)), None)
        if error is not None:
            where = "/".join(map(str, error.path)) or "<root>"
            raise MockDataError(f"{file_name}[{index}] {where}: {error.message}")
    return items


def _require_keys(obj, keys: tuple[str, ...], file_name: str) -> dict:
    if not isinstance(obj, dict) or any(k not in obj for k in keys):
        raise MockDataError(f"{file_name}: expected an object with keys {', '.join(keys)}")
    return obj


def load_mock_data(contracts_dir: Path) -> MockData:
    """Read every mock the server needs and validate it against contracts/schemas."""
    mocks = Path(contracts_dir) / "mocks"
    finding_v = _validator(contracts_dir, "finding.schema.json")
    document_v = _validator(contracts_dir, "scraped-document.schema.json")
    source_v = _validator(contracts_dir, "source.schema.json")
    events_v = _validator(contracts_dir, "events.schema.json")

    findings = _validate_items(_require_keys(_read_json(mocks / "findings.json"), ("items",), "findings.json")["items"],
                               finding_v, "findings.json")
    documents = _validate_items(_read_json(mocks / "documents.json"), document_v, "documents.json")
    sources = _validate_items(_require_keys(_read_json(mocks / "sources.json"), ("items",), "sources.json")["items"],
                              source_v, "sources.json")
    events = _validate_items(_read_json(mocks / "events.json"), events_v, "events.json")
    trend = _require_keys(_read_json(mocks / "trend.json"), ("bucket", "points"), "trend.json")
    calibration = {
        m: _require_keys(_read_json(mocks / f"calibration-{m}.json"), ("module", "points"), f"calibration-{m}.json")
        for m in MODULES
    }
    thresholds = _require_keys(_read_json(mocks / "thresholds.json"), MODULES, "thresholds.json")
    health = _require_keys(_read_json(mocks / "health.json"), ("status", "services"), "health.json")

    doc_ids = {d["id"] for d in documents}
    for f in findings:
        if f["document_id"] not in doc_ids:
            raise MockDataError(f"findings.json: finding {f['id']} references unknown document {f['document_id']}")

    return MockData(findings, documents, sources, events, trend, calibration,
                    {m: float(thresholds[m]) for m in MODULES}, health)


def risk_level(score: float, threshold: float) -> str:
    if score >= threshold:
        return "high"
    if score >= round(threshold - MEDIUM_BAND, 6):
        return "medium"
    return "low"


class Store:
    """Mutable in-memory copy of the mock data; `reset()` restores the original."""

    def __init__(self, data: MockData):
        self._original = data
        self.reset()

    def reset(self) -> None:
        data = copy.deepcopy(self._original)
        self.findings: dict[str, dict] = {}
        for f in data.findings:
            f.pop("risk_level", None)  # derived at read time from the current thresholds
            self.findings[f["id"]] = f
        self.documents: dict[str, dict] = {d["id"]: d for d in data.documents}
        self.sources: dict[str, dict] = {s["id"]: s for s in data.sources}
        self.thresholds: dict[str, float] = dict(data.thresholds)
        self.trend: dict = data.trend
        self.calibration: dict[str, dict] = data.calibration
        self.health: dict = data.health
        self.events: list[dict] = data.events

    def risk_level_of(self, finding: dict) -> str:
        return risk_level(finding["score"], self.thresholds[finding["module"]])

    def finding_view(self, finding: dict) -> dict:
        view = dict(finding)
        view["risk_level"] = self.risk_level_of(finding)
        return view
