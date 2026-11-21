"""Gold-set file `analytics/eval/gold.jsonl`: load and validate every line before anything is analyzed.

One JSON object per line (labeling guide: `analytics/eval/` README; spec: gold-set-evaluation):
`{id, origin, basis, hard_case?, document: ScrapedDocument, expect: {M1|M2|M3: {label, rules?}}}`.
All problems are collected and raised together as `GoldError`. Messages name the line, the gold id and the
field, never document text (the scraped-text rule applies to UKNF samples too).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..models import ScrapedDocument
from .known_ids import MODULES, Catalogues, known_ids

ORIGINS = ("synthetic", "uknf-sample", "zasob-example")
DOC_LABELS = ("negative", "positive")
RULE_LABELS = ("fail", "not_applicable", "pass")
ITEM_FIELDS = {"id", "origin", "basis", "hard_case", "document", "expect"}
EXPECT_FIELDS = {"label", "rules"}


class _Object(dict):
    """A JSON object that remembers repeated keys (`json.loads` would silently keep the last value)."""

    duplicates: tuple[str, ...] = ()


def _object(pairs: list[tuple[str, Any]]) -> _Object:
    obj = _Object(pairs)
    keys = [k for k, _ in pairs]
    obj.duplicates = tuple(sorted({k for k in keys if keys.count(k) > 1}))
    return obj


def _duplicates(value: Any, where: str) -> list[str]:
    return [f"{where}{k}: duplicate key" for k in getattr(value, "duplicates", ())]


class GoldError(ValueError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class ModuleExpectation:
    label: str
    rules: dict[str, str] = field(default_factory=dict)

    @property
    def positive(self) -> bool:
        return self.label == "positive"


@dataclass(frozen=True)
class GoldItem:
    line: int
    id: str
    origin: str
    basis: str
    hard_case: str | None
    document: ScrapedDocument
    expect: dict[str, ModuleExpectation]


def rule_status(module: str, rule_id: str, catalogues: Catalogues) -> str:
    """`implemented`, `not_implemented` (in the catalogue, switched off) or `not_in_build` (no entry)."""
    catalogue = catalogues.get(module) or {}
    if rule_id not in catalogue:
        return "not_in_build"
    return "implemented" if catalogue[rule_id] else "not_implemented"


def _one_of(value: Any, allowed: tuple[str, ...]) -> str | None:
    if isinstance(value, str) and value in allowed:
        return None
    return f"{value!r} is not one of {', '.join(allowed)}"


def load_gold(path: Path, catalogues: Catalogues) -> list[GoldItem]:
    try:
        raw = Path(path).read_bytes().decode("utf-8-sig")  # no newline translation: line numbers stay exact
    except (OSError, UnicodeDecodeError) as exc:
        reason = exc.strerror if isinstance(exc, OSError) else "not UTF-8"
        raise GoldError([f"{path}: cannot read gold set ({reason})"]) from None
    known = known_ids(catalogues)
    owner = {rid: m for m in MODULES for rid in known[m]}
    problems: list[str] = []
    items: list[GoldItem] = []
    first_line: dict[str, int] = {}
    # Split on LF only: str.splitlines() also breaks on U+2028, U+0085 and others, which json.dumps with
    # ensure_ascii=False leaves raw inside strings (scraped text carries them).
    for number, text in enumerate(raw.split("\n"), start=1):
        text = text.removesuffix("\r")
        if not text.strip():
            continue
        try:
            data = json.loads(text, object_pairs_hook=_object)
        except json.JSONDecodeError as exc:
            problems.append(f"line {number}: invalid JSON ({exc.msg} at column {exc.colno})")
            continue
        if not isinstance(data, dict):
            problems.append(f"line {number}: not a JSON object")
            continue
        item, item_problems = _parse(number, data, known, owner)
        gid = data.get("id")
        if isinstance(gid, str) and gid:
            if gid in first_line:
                item_problems.append(f"id: duplicate of line {first_line[gid]}")
            else:
                first_line[gid] = number
        prefix = f"line {number} ({gid})" if isinstance(gid, str) and gid else f"line {number}"
        problems.extend(f"{prefix}: {p}" for p in item_problems)
        if item is not None:  # any problem raises below, so a kept item is never returned with one
            items.append(item)
    if not problems and not items:
        problems.append("no labeled document")
    if problems:
        raise GoldError(problems)
    return items


def _parse(number: int, data: dict, known: dict[str, set[str]], owner: dict[str, str]) -> tuple[GoldItem | None, list[str]]:
    problems = _duplicates(data, "") + [f"{k}: unknown field" for k in sorted(set(data) - ITEM_FIELDS)]
    gid = data.get("id")
    if not isinstance(gid, str) or not gid:
        problems.append("id: must be a non-empty string")
        gid = None
    if (p := _one_of(data.get("origin"), ORIGINS)) is not None:
        problems.append(f"origin: {p}")
    basis = data.get("basis")
    if not isinstance(basis, str) or not basis.strip():
        problems.append("basis: must be a non-empty string")
    hard_case = data.get("hard_case")
    if hard_case is not None and not isinstance(hard_case, str):
        problems.append("hard_case: must be a string")
    document = None
    try:
        document = ScrapedDocument.model_validate(data.get("document"))
    except ValidationError as exc:
        # Locations and messages only: errors(include_input=False) never echoes the document's values.
        for e in exc.errors(include_input=False, include_url=False):
            where = ".".join(str(x) for x in ("document", *e["loc"]))
            problems.append(f"{where}: {e['type']}")
    expect = _expectations(data.get("expect"), known, owner, problems)
    if gid is None or document is None or expect is None:
        return None, problems
    return GoldItem(number, gid, data["origin"], basis, hard_case, document, expect), problems


def _expectations(raw: Any, known: dict[str, set[str]], owner: dict[str, str],
                  problems: list[str]) -> dict[str, ModuleExpectation] | None:
    if not isinstance(raw, dict):
        problems.append("expect: must be an object")
        return None
    if not raw:
        problems.append("expect: no module labeled")
        return None
    problems.extend(_duplicates(raw, "expect."))
    out: dict[str, ModuleExpectation] = {}
    for module, value in raw.items():
        where = f"expect.{module}"
        if module not in MODULES:
            problems.append(f"{where}: unknown module (allowed: {', '.join(MODULES)})")
            continue
        if not isinstance(value, dict):
            problems.append(f"{where}: must be an object")
            continue
        problems.extend(f"{where}.{k}: unknown field" for k in sorted(set(value) - EXPECT_FIELDS))
        if (p := _one_of(value.get("label"), DOC_LABELS)) is not None:
            problems.append(f"{where}.label: {p}")
        rules = value.get("rules", {})
        if not isinstance(rules, dict):
            problems.append(f"{where}.rules: must be an object")
            continue
        problems.extend(_duplicates(rules, f"{where}.rules."))
        for rule_id, label in rules.items():
            if rule_id not in known[module]:
                other = owner.get(rule_id)
                reason = f"rule id of {other}, not {module}" if other else f"unknown rule id for {module}"
                problems.append(f"{where}.rules.{rule_id}: {reason}")
            elif (p := _one_of(label, RULE_LABELS)) is not None:
                problems.append(f"{where}.rules.{rule_id}: {p}")
        out[module] = ModuleExpectation(value.get("label"), dict(rules))
    return out
