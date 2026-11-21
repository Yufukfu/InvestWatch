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


def _assert_round_trip(got: dict, mock: dict, derived=()) -> None:
    """The read-back equals the mock key by key, explicit nulls included: a mock null must come back as
    null or as an absent key (columns omit nulls in `*_to_contract`, payload keys keep them). Only
    API-derived keys are left out, and the read-back may not carry a key the mock does not have."""
    expected = {k: v for k, v in mock.items() if k not in derived}
    assert set(got) <= set(expected), set(got) - set(expected)
    assert {k: got.get(k) for k in expected} == expected


NULLABLE_JSONB = ("firm", "advertiser", "model")


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
        # A mock's explicit null must be SQL NULL in the column, not the JSON value null.
        explicit_nulls = [(f["id"], c) for f in finds for c in NULLABLE_JSONB if c in f and f[c] is None]
        assert explicit_nulls, "the mocks no longer carry an explicit null JSONB field"
        for fid, col in explicit_nulls:
            q = select(findings.c[col].is_(None)).where(findings.c.id == fid)
            assert conn.execute(q).scalar_one(), (fid, col)

    assert len(back_s) == len(srcs) and len(back_d) == len(docs) and len(back_f) == len(finds)
    for s in srcs:
        got = next(v for v in back_s.values() if v["id"] == s["id"])
        _assert_round_trip(got, s, DERIVED["sources"])
        assert_contract_valid("source", {**got, "documents_count": 0})
    for d in docs:
        got = next(v for v in back_d.values() if v["id"] == d["id"])
        _assert_round_trip(got, d)
        assert_contract_valid("scraped-document", got)
    for f in finds:
        got = next(v for v in back_f.values() if v["id"] == f["id"])
        _assert_round_trip(got, f, DERIVED["findings"])
        assert_contract_valid("finding", got)


def test_time_round_trip_keeps_utc_z():
    assert format_time(parse_time("2026-11-21T15:00:40Z")) == "2026-11-21T15:00:40Z"
    assert format_time(parse_time("2026-11-21T16:00:40+01:00")) == "2026-11-21T15:00:40Z"
    assert format_time(parse_time("2026-11-21T15:00:40.250Z")) == "2026-11-21T15:00:40.250000Z"
    assert format_time(parse_time("2026-11-21T15:00:40.123456Z")) == "2026-11-21T15:00:40.123456Z"


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
