"""Validate HTTP responses against the response schemas in contracts/openapi.yaml.

External refs like './schemas/finding.schema.json' are inlined; those schemas carry their own `$id`,
so their internal `#/$defs/...` refs resolve inside them, while `#/components/...` resolves against the
OpenAPI document itself (registered as urn:openapi).
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

CONTRACTS_DIR = Path(__file__).resolve().parents[2]


def _schema_ids() -> dict[str, dict]:
    """Every contracts/schemas file, keyed by the relative ref used in openapi.yaml."""
    out = {}
    for path in (CONTRACTS_DIR / "schemas").glob("*.schema.json"):
        out[f"./schemas/{path.name}"] = json.loads(path.read_text(encoding="utf-8"))
    return out


def _rewrite_refs(node, schemas: dict[str, dict]):
    """Point file refs at the schemas' own $id so the registry resolves them (and their $defs)."""
    if isinstance(node, dict):
        out = {k: _rewrite_refs(v, schemas) for k, v in node.items()}
        ref = node.get("$ref")
        base, _, fragment = ref.partition("#") if isinstance(ref, str) else ("", "", "")
        if base in schemas:
            out["$ref"] = schemas[base]["$id"] + (f"#{fragment}" if fragment else "")
        return out
    if isinstance(node, list):
        return [_rewrite_refs(v, schemas) for v in node]
    return node


@lru_cache(maxsize=1)
def _registry() -> Registry:
    schemas = _schema_ids()
    spec = yaml.safe_load((CONTRACTS_DIR / "openapi.yaml").read_text(encoding="utf-8"))
    spec = _rewrite_refs(copy.deepcopy(spec), schemas)
    resources = [("urn:openapi", Resource.from_contents(spec, default_specification=DRAFT202012))]
    resources += [(s["$id"], Resource.from_contents(s)) for s in schemas.values()]
    return Registry().with_resources(resources)


def _pointer(*parts: str) -> str:
    return "/".join(p.replace("~", "~0").replace("/", "~1") for p in parts)


def _response_pointer(path: str, method: str, status: int) -> str:
    """JSON pointer to the response schema, following `$ref: '#/components/responses/...'`."""
    spec = yaml.safe_load((CONTRACTS_DIR / "openapi.yaml").read_text(encoding="utf-8"))
    response = spec["paths"][path][method]["responses"][str(status)]
    ref = response.get("$ref")
    if ref:
        parts = ref.removeprefix("#/").split("/")
        return _pointer(*parts, "content", "application/json", "schema")
    return _pointer("paths", path, method, "responses", str(status), "content", "application/json", "schema")


def response_errors(path: str, method: str, status: int, body) -> list[str]:
    pointer = _response_pointer(path, method, status)
    validator = Draft202012Validator({"$ref": f"urn:openapi#/{pointer}"}, registry=_registry(),
                                     format_checker=FormatChecker())
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in validator.iter_errors(body)]


def assert_response_matches(path: str, method: str, response) -> None:
    errors = response_errors(path, method, response.status_code, response.json())
    assert not errors, f"{method.upper()} {path} -> {response.status_code} violates openapi.yaml: {errors}"
