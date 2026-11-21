"""Validate mock data (and optionally any JSON file) against the v1 contracts.

    pip install -r contracts/requirements.txt
    python contracts/validate.py                       # validate all mocks
    python contracts/validate.py finding my.json       # validate a file (object or list) against one schema

Schemas: document, finding, source, events.
Exit code 1 on any validation error - usable in CI and pre-merge checks.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent
SCHEMAS = {
    "document": "scraped-document.schema.json",
    "finding": "finding.schema.json",
    "source": "source.schema.json",
    "events": "events.schema.json",
}


def validator(name: str) -> Draft202012Validator:
    schema = json.loads((ROOT / "schemas" / SCHEMAS[name]).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def check(name: str, items: list, label: str) -> int:
    v = validator(name)
    errors = 0
    for i, item in enumerate(items):
        for err in sorted(v.iter_errors(item), key=lambda e: list(e.path)):
            path = "/".join(str(p) for p in err.path) or "<root>"
            print(f"  FAIL {label}[{i}] {path}: {err.message}")
            errors += 1
    print(f"{'ok  ' if not errors else 'FAIL'} {label}: {len(items)} item(s) vs {SCHEMAS[name]}")
    return errors


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_mocks() -> int:
    m = ROOT / "mocks"
    errors = 0
    errors += check("document", load(m / "documents.json"), "documents.json")
    errors += check("finding", load(m / "findings.json")["items"], "findings.json")
    errors += check("source", load(m / "sources.json")["items"], "sources.json")
    errors += check("events", load(m / "events.json"), "events.json")

    detail = load(m / "finding-detail.json")
    document = detail.pop("document")
    detail.pop("screenshot_urls")
    errors += check("finding", [detail], "finding-detail.json (finding part)")
    errors += check("document", [document], "finding-detail.json (document part)")

    # referential integrity between mocks
    doc_ids = {d["id"] for d in load(m / "documents.json")}
    src_ids = {s["id"] for s in load(m / "sources.json")["items"]}
    for f in load(m / "findings.json")["items"]:
        if f["document_id"] not in doc_ids:
            print(f"  FAIL finding {f['id']} references unknown document {f['document_id']}")
            errors += 1
    for d in load(m / "documents.json"):
        if d["source_id"] and d["source_id"] not in src_ids:
            print(f"  FAIL document {d['id']} references unknown source {d['source_id']}")
            errors += 1

    spec = yaml.safe_load((ROOT / "openapi.yaml").read_text(encoding="utf-8"))
    print(f"ok   openapi.yaml: {spec['openapi']}, {len(spec['paths'])} paths")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) == 3:
        name, path = argv[1], Path(argv[2])
        data = load(path)
        errors = check(name, data if isinstance(data, list) else [data], path.name)
    else:
        errors = validate_mocks()
    print("\nAll contracts valid." if not errors else f"\n{errors} error(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
