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


def _formatted(msg: str, exc: BaseException | None = None) -> dict:
    exc_info = (type(exc), exc, None) if exc else None
    record = logging.LogRecord("iw", logging.ERROR, __file__, 1, msg, (), exc_info)
    return json.loads(JsonFormatter().format(record))


def test_url_credentials_are_redacted_in_message_and_exception():
    entry = _formatted("connect postgresql://iw_admin:s3cret@postgres:5432/db failed",
                       RuntimeError("redis://:hunter2@redis:6379/0 refused"))
    line = json.dumps(entry)
    assert "s3cret" not in line and "hunter2" not in line
    assert "postgresql://***@postgres:5432/db" in entry["msg"]


@pytest.mark.parametrize("password", ["pa/ss", "p@ss@word", "a:b/c@d"])
def test_unencoded_special_characters_in_password_are_redacted(password):
    entry = _formatted(f"connect postgresql://iw_admin:{password}@postgres:5432/db failed")
    # The whole message: user, every fragment of the password, host and the rest are checked exactly.
    assert entry["msg"] == "connect postgresql://***@postgres:5432/db failed"


def test_two_urls_in_one_line_are_both_redacted():
    entry = _formatted("from postgresql://u:p@ss@a:5432/x to redis://:h@nter@redis:6379/0")
    assert entry["msg"] == "from postgresql://***@a:5432/x to redis://***@redis:6379/0"


def test_sql_parameters_are_redacted():
    entry = _formatted("x", RuntimeError("(psycopg.errors.CheckViolation) boom\n[SQL: INSERT ...]\n"
                                         "[parameters: {'note': 'private analyst note'}]\n(Background on this error)"))
    assert "private analyst note" not in entry["exc"]
    assert "[parameters: redacted]" in entry["exc"]


def test_unserialisable_extra_does_not_drop_the_line():
    record = logging.LogRecord("iw", logging.INFO, __file__, 1, "ok", (), None)
    record.status = object()
    assert json.loads(JsonFormatter().format(record))["msg"] == "ok"
