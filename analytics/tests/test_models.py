from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from conftest import NOW, make_doc
from investwatch_analytics.models import Finding, FirmRef, ModelInfo, RuleResult, ScrapedDocument


def sample_finding() -> Finding:
    return Finding(
        id=str(uuid.uuid4()),
        document_id="11111111-1111-4111-8111-111111111111",
        module="M2",
        score=0.5,
        status="new",
        title="Tytuł",
        summary="Podsumowanie.",
        firm=FirmRef(name="Alfa", registry_id=None, registry_type="brokerage_house", authorized=True, match_confidence=0.95),
        rules=[RuleResult(rule_id="R2", name="Oznaczenie reklamy", result="fail", severity="medium", method="rule")],
        content_excerpt="x",
        url="https://example.com/oferta",
        platform="web",
        detected_at=NOW,
        updated_at=NOW,
        model=ModelInfo(pipeline_version="0.1.0", llm=None, embedder=None),
    )


def test_finding_matches_contract(finding_validator):
    payload = sample_finding().to_contract()
    errors = [e.message for e in finding_validator.iter_errors(payload)]
    assert errors == []
    assert "risk_level" not in payload


def test_timestamps_are_utc_z():
    payload = sample_finding().to_contract()
    assert payload["detected_at"] == "2026-11-21T16:00:00Z"
    assert payload["updated_at"].endswith("Z")


def test_finding_rejects_unknown_field():
    data = sample_finding().model_dump()
    data["risk_level"] = "high"
    with pytest.raises(ValidationError):
        Finding(**data)


def test_rule_id_pattern_enforced():
    with pytest.raises(ValidationError):
        RuleResult(rule_id="R19", name="x", result="fail", severity="low")


def test_all_mock_documents_parse(mock_documents):
    parsed = [ScrapedDocument.model_validate(d) for d in mock_documents]
    assert len(parsed) == len(mock_documents) > 0


def test_unknown_field_is_ignored():
    doc = ScrapedDocument.model_validate(make_doc(future_field={"a": 1}))
    assert not hasattr(doc, "future_field")


@pytest.mark.parametrize("field,value", [("text", None), ("fetched_at", "yesterday")])
def test_missing_or_malformed_required_field(field, value):
    data = make_doc()
    if value is None:
        del data[field]
    else:
        data[field] = value
    with pytest.raises(ValidationError) as exc:
        ScrapedDocument.model_validate(data)
    assert field in str(exc.value)


def test_unknown_source_kind_rejected():
    with pytest.raises(ValidationError):
        ScrapedDocument.model_validate(make_doc(source_kind="partner"))
