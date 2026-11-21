from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from iw_mock_server.logging_setup import JsonFormatter
from iw_mock_server.settings import Settings


def test_defaults_point_at_the_contracts_dir(monkeypatch):
    for var in ("MOCK_PORT", "MOCK_CORS_ORIGINS", "CONTRACTS_DIR", "MOCK_REPLAY_INTERVAL_S"):
        monkeypatch.delenv(var, raising=False)

    s = Settings()

    assert s.port == 8000
    assert (s.contracts_dir / "openapi.yaml").is_file()
    assert "http://localhost:5173" in s.cors_origins


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("MOCK_PORT", "9001")
    monkeypatch.setenv("MOCK_CORS_ORIGINS", " http://a.test , ,http://b.test ")
    monkeypatch.setenv("CONTRACTS_DIR", str(tmp_path))
    monkeypatch.setenv("MOCK_REPLAY_INTERVAL_S", "0")

    s = Settings()

    assert s.port == 9001
    assert s.cors_origins == ("http://a.test", "http://b.test")
    assert s.contracts_dir == Path(str(tmp_path))
    assert s.replay_interval_s == 0


@pytest.mark.parametrize(("var", "value"), [("MOCK_PORT", "abc"), ("MOCK_REPLAY_INTERVAL_S", "-1"),
                                            ("MOCK_SCAN_DELAY_S", "soon")])
def test_bad_env_value_names_the_variable(monkeypatch, var, value):
    monkeypatch.setenv(var, value)

    with pytest.raises(ValueError, match=var):
        Settings()


def test_json_formatter_emits_one_json_object():
    record = logging.LogRecord("iw", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    record.path = "/api/findings"

    entry = json.loads(JsonFormatter().format(record))

    assert entry["msg"] == "hello world"
    assert entry["level"] == "INFO"
    assert entry["path"] == "/api/findings"
    assert entry["ts"].endswith("Z")
