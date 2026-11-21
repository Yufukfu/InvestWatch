"""Scenario 'Contract mock round-trips' (specs/database-schema, requirement 'Columns follow the contracts')."""

from __future__ import annotations

import json

from sqlalchemy import insert, select

from conftest import CONTRACTS_DIR, assert_contract_valid
from investwatch_api.db.mapping import (
    DERIVED,
    document_to_contract,
    document_to_row,
    finding_to_contract,
    finding_to_row,
    format_time,
    parse_time,
    source_to_contract,
    source_to_row,
)
from investwatch_api.db.tables import documents, findings, sources


def _mock(name):
    data = json.loads((CONTRACTS_DIR / "mocks" / name).read_text(encoding="utf-8"))
    return data["items"] if isinstance(data, dict) else data


def _without(obj: dict, keys=()) -> dict:
    """Null-valued keys and API-derived keys are not stored, so they are not compared."""
    return {k: v for k, v in obj.items() if v is not None and k not in keys}


def test_contract_mock_round_trips(app_engine):
    srcs, docs, finds = _mock("sources.json"), _mock("documents.json"), _mock("findings.json")
    with app_engine.begin() as conn:
        for s in srcs:
            conn.execute(insert(sources).values(source_to_row(s)))
        for d in docs:
            conn.execute(insert(documents).values(document_to_row(d)))
        for f in finds:
            conn.execute(insert(findings).values(finding_to_row(f)))

        back_s = {r["id"]: source_to_contract(r) for r in conn.execute(select(sources)).mappings()}
        back_d = {r["id"]: document_to_contract(r) for r in conn.execute(select(documents)).mappings()}
        back_f = {r["id"]: finding_to_contract(r) for r in conn.execute(select(findings)).mappings()}

    assert len(back_s) == len(srcs) and len(back_d) == len(docs) and len(back_f) == len(finds)
    for s in srcs:
        got = next(v for v in back_s.values() if v["id"] == s["id"])
        assert _without(got) == _without(s, DERIVED["sources"])
        assert_contract_valid("source", {**got, "documents_count": 0})
    for d in docs:
        got = next(v for v in back_d.values() if v["id"] == d["id"])
        assert _without(got) == _without(d)
        assert_contract_valid("scraped-document", got)
    for f in finds:
        got = next(v for v in back_f.values() if v["id"] == f["id"])
        assert _without(got) == _without(f, DERIVED["findings"])
        assert_contract_valid("finding", got)


def test_time_round_trip_keeps_utc_z():
    assert format_time(parse_time("2026-11-21T15:00:40Z")) == "2026-11-21T15:00:40Z"
    assert format_time(parse_time("2026-11-21T16:00:40+01:00")) == "2026-11-21T15:00:40Z"
    assert format_time(parse_time("2026-11-21T15:00:40.250Z")) == "2026-11-21T15:00:40.250Z"


def test_unknown_payload_keys_are_not_returned():
    row = {**{k: None for k in ("id", "source_id", "platform", "source_kind", "url", "canonical_url",
                                "fetched_at", "published_at", "http_status", "lang", "title", "text",
                                "content_hash", "html_object_key")},
           "payload": {"links": [], "secret": "x"}}
    assert document_to_contract(row) == {"links": []}


def test_malformed_id_is_rejected_before_insert():
    import pytest

    with pytest.raises(ValueError):
        finding_to_row({"id": "not-a-uuid", "document_id": "also-not"})


def test_naive_timestamp_is_read_as_utc():
    from datetime import timezone

    assert parse_time("2026-11-21T15:00:40").tzinfo == timezone.utc
    assert format_time(parse_time("2026-11-21T15:00:40")) == "2026-11-21T15:00:40Z"
