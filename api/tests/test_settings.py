import json
import logging

import pytest

from investwatch_api.logging_setup import JsonFormatter
from investwatch_api.settings import ConfigError, admin_database_url, app_database_url


def test_missing_admin_url_names_the_variable(monkeypatch):
    monkeypatch.delenv("DATABASE_ADMIN_URL", raising=False)
    with pytest.raises(ConfigError, match="DATABASE_ADMIN_URL"):
        admin_database_url()


def test_admin_url_does_not_fall_back_to_app_url(monkeypatch):
    monkeypatch.delenv("DATABASE_ADMIN_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://iw_app:x@db/investwatch")
    with pytest.raises(ConfigError, match="DATABASE_ADMIN_URL"):
        admin_database_url()


def test_blank_value_counts_as_missing(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "   ")
    with pytest.raises(ConfigError, match="DATABASE_URL is not set"):
        app_database_url()


def test_surrounding_whitespace_is_ignored(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "  postgresql://u:p@h/db\t")
    assert app_database_url() == "postgresql+psycopg://u:p@h/db"


@pytest.mark.parametrize("raw, expected", [
    ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
])
def test_url_is_normalised_to_psycopg(monkeypatch, raw, expected):
    monkeypatch.setenv("DATABASE_ADMIN_URL", raw)
    assert admin_database_url() == expected


def test_config_error_never_contains_the_password(monkeypatch):
    monkeypatch.setenv("DATABASE_ADMIN_URL", "mysql://u:s3cret@h/db")
    with pytest.raises(ConfigError) as exc:
        admin_database_url()
    assert "s3cret" not in str(exc.value)


def test_json_formatter_emits_one_json_object():
    record = logging.LogRecord("iw", logging.WARNING, __file__, 1, "hello %s", ("world",), None)
    entry = json.loads(JsonFormatter().format(record))
    assert entry["level"] == "WARNING"
    assert entry["msg"] == "hello world"
    assert entry["ts"].endswith("Z")
