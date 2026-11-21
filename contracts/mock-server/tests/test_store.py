from __future__ import annotations

import json

import pytest

from conftest import assert_valid
from iw_mock_server.store import MockDataError, Store, load_mock_data, risk_level


def test_loads_all_mock_files_and_they_match_the_schemas(contracts_dir):
    data = load_mock_data(contracts_dir)

    assert len(data.findings) == 9
    assert len(data.documents) == 9
    assert len(data.sources) == 4
    for finding in data.findings:
        assert_valid("finding", finding)
    for document in data.documents:
        assert_valid("scraped-document", document)
    for source in data.sources:
        assert_valid("source", source)
    for event in data.events:
        assert_valid("events", event)
    assert set(data.calibration) == {"M1", "M2", "M3"}
    assert data.thresholds == {"M1": 0.6, "M2": 0.5, "M3": 0.7}


def test_missing_mock_file_names_the_file(contracts_copy):
    (contracts_copy / "mocks" / "findings.json").unlink()

    with pytest.raises(MockDataError, match="findings.json"):
        load_mock_data(contracts_copy)


def test_invalid_item_names_the_file(contracts_copy):
    path = contracts_copy / "mocks" / "findings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["items"][0]["module"] = "M9"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(MockDataError, match="findings.json"):
        load_mock_data(contracts_copy)


def test_unparsable_json_names_the_file(contracts_copy):
    (contracts_copy / "mocks" / "sources.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(MockDataError, match="sources.json"):
        load_mock_data(contracts_copy)


@pytest.mark.parametrize(
    ("score", "threshold", "expected"),
    [(0.9, 0.9, "high"), (0.95, 0.9, "high"), (0.7, 0.9, "medium"), (0.89, 0.9, "medium"), (0.69, 0.9, "low"), (0.0, 0.5, "low")],
)
def test_risk_level_follows_the_threshold(score, threshold, expected):
    assert risk_level(score, threshold) == expected


def test_store_does_not_share_state_with_loaded_data_and_resets(contracts_dir):
    data = load_mock_data(contracts_dir)
    store = Store(data)
    first_id = next(iter(store.findings))

    store.findings[first_id]["status"] = "closed"
    store.thresholds["M2"] = 0.9

    original_status = next(f["status"] for f in data.findings if f["id"] == first_id)
    assert original_status != "closed"
    store.reset()
    assert store.findings[first_id]["status"] == original_status
    assert store.thresholds["M2"] == 0.5


def test_store_findings_carry_no_stored_risk_level(contracts_dir):
    store = Store(load_mock_data(contracts_dir))

    assert all("risk_level" not in f for f in store.findings.values())
