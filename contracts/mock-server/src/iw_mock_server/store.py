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


def _check_thresholds(obj, file_name: str) -> dict[str, float]:
    _require_keys(obj, MODULES, file_name)
    for m in MODULES:
        value = obj[m]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise MockDataError(f"{file_name}: {m} must be a number between 0 and 1, got {value!r}")
    return {m: float(obj[m]) for m in MODULES}


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_points(points, integers: tuple[str, ...], numbers: tuple[str, ...], file_name: str,
                  required: tuple[str, ...] = ()) -> None:
    """Point shapes from openapi.yaml: counts are integers, ratios and thresholds are numbers."""
    if not isinstance(points, list):
        raise MockDataError(f"{file_name}: points must be a list")
    for index, point in enumerate(points):
        where = f"{file_name} points[{index}]"
        _require_keys(point, (*required, *integers, *numbers), where)
        for k in integers:
            if not _is_int(point[k]):
                raise MockDataError(f"{where}.{k} must be an integer, got {point[k]!r}")
        for k in numbers:
            if not _is_number(point[k]):
                raise MockDataError(f"{where}.{k} must be a number, got {point[k]!r}")


def load_mock_data(contracts_dir: Path) -> MockData:
    """Read every mock the server needs and validate it against contracts/schemas."""
    mocks = Path(contracts_dir) / "mocks"
    finding_v = _validator(contracts_dir, "finding.schema.json")
    document_v = _validator(contracts_dir, "scraped-document.schema.json")
    source_v = _validator(contracts_dir, "source.schema.json")
    events_v = _validator(contracts_dir, "events.schema.json")

    findings = _validate_items(_require_keys(_read_json(mocks / "findings.json"), ("items",), "findings.json")["items"],
                               finding_v, "findings.json")
    if not findings:  # replay clones mock findings; with none, every replay tick would fail
        raise MockDataError("findings.json: at least one finding is required")
    documents = _validate_items(_read_json(mocks / "documents.json"), document_v, "documents.json")
    sources = _validate_items(_require_keys(_read_json(mocks / "sources.json"), ("items",), "sources.json")["items"],
                              source_v, "sources.json")
    events = _validate_items(_read_json(mocks / "events.json"), events_v, "events.json")
    trend = _require_keys(_read_json(mocks / "trend.json"), ("bucket", "points"), "trend.json")
    calibration = {
        m: _require_keys(_read_json(mocks / f"calibration-{m}.json"), ("module", "points"), f"calibration-{m}.json")
        for m in MODULES
    }
    _check_points(trend["points"], MODULES, (), "trend.json", required=("t",))
    for m, cal in calibration.items():
        file_name = f"calibration-{m}.json"
        if not _is_int(cal.get("labeled_samples")):
            raise MockDataError(f"{file_name}: labeled_samples must be an integer")
        _check_points(cal["points"], ("tp", "fp", "fn", "tn"), ("threshold", "precision", "recall"), file_name)
    thresholds = _check_thresholds(_read_json(mocks / "thresholds.json"), "thresholds.json")
    health = _require_keys(_read_json(mocks / "health.json"), ("status", "services"), "health.json")

    doc_ids = {d["id"] for d in documents}
    for f in findings:
        if f["document_id"] not in doc_ids:
            raise MockDataError(f"findings.json: finding {f['id']} references unknown document {f['document_id']}")

    return MockData(findings, documents, sources, events, trend, calibration, thresholds, health)


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
        self.generation = 0
        self.reset()

    def reset(self) -> None:
        """Restore the original data. Everything is built first and swapped in at the end, and
        `generation` changes, so background work started before the reset can tell."""
        data = copy.deepcopy(self._original)
        findings = {}
        for f in data.findings:
            f.pop("risk_level", None)  # derived at read time from the current thresholds
            findings[f["id"]] = f
        self.findings: dict[str, dict] = findings
        self.documents: dict[str, dict] = {d["id"]: d for d in data.documents}
        self.sources: dict[str, dict] = {s["id"]: s for s in data.sources}
        self.thresholds: dict[str, float] = dict(data.thresholds)
        self.trend: dict = data.trend
        self.calibration: dict[str, dict] = data.calibration
        self.health: dict = data.health
        self.events: list[dict] = data.events
        self.added_ids: set[str] = set()
        self.generation += 1

    def add_finding(self, finding: dict) -> None:
        """Add a finding created at runtime (replay); it also counts in the trend."""
        self.findings[finding["id"]] = finding
        self.added_ids.add(finding["id"])

    def trend_points(self, risk_level_filter: str | None = None) -> list[dict]:
        """Hourly points: the mock trend plus findings added at runtime.

        With a risk-level filter the mock background counts cannot be split by risk, so the points
        are recomputed from the findings themselves over the same hourly buckets.
        """
        base = [dict(p) for p in self.trend["points"]]
        if risk_level_filter:
            for p in base:
                for m in MODULES:
                    p[m] = 0
            counted = [f for f in self.findings.values() if self.risk_level_of(f) == risk_level_filter]
        else:
            counted = [self.findings[i] for i in self.added_ids if i in self.findings]

        by_hour = {p["t"]: p for p in base}
        for f in counted:
            hour = f["detected_at"][:13] + ":00:00Z"
            point = by_hour.get(hour)
            if point is None:
                point = by_hour[hour] = {"t": hour, **{m: 0 for m in MODULES}}
                base.append(point)
            point[f["module"]] += 1
        return sorted(base, key=lambda p: p["t"])

    def risk_level_of(self, finding: dict) -> str:
        return risk_level(finding["score"], self.thresholds[finding["module"]])

    def finding_view(self, finding: dict) -> dict:
        view = dict(finding)
        view["risk_level"] = self.risk_level_of(finding)
        return view
