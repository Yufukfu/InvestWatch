import pytest

from iw_scraper.jobs import QueueSettings
from iw_scraper.worker import RunnerSettings


def test_unset_variables_keep_the_defaults(monkeypatch):
    monkeypatch.delenv("SCRAPER_MAX_TRIES", raising=False)

    assert QueueSettings.from_env() == QueueSettings()


def test_variables_override_fields_with_the_field_type(monkeypatch):
    monkeypatch.setenv("SCRAPER_MAX_TRIES", "7")
    monkeypatch.setenv("SCRAPER_BACKOFF_BASE", "0.5")

    settings = QueueSettings.from_env()

    assert (settings.max_tries, settings.backoff_base) == (7, 0.5)
    assert settings.attempt_timeout == QueueSettings().attempt_timeout


def test_a_bad_value_names_the_variable(monkeypatch):
    monkeypatch.setenv("SCRAPER_MAX_TRIES", "three")

    with pytest.raises(ValueError, match="SCRAPER_MAX_TRIES") as error:
        QueueSettings.from_env()

    assert "three" not in str(error.value)  # a bad value may be a secret pasted into the wrong variable


def test_the_runner_needs_redis_url_and_reads_the_rest(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        RunnerSettings.from_env()

    monkeypatch.setenv("REDIS_URL", "redis://cache:6379/1")
    monkeypatch.setenv("SCRAPER_SHUTDOWN_DEADLINE", "12.5")
    settings = RunnerSettings.from_env()

    assert (settings.redis_url, settings.shutdown_deadline) == ("redis://cache:6379/1", 12.5)


def test_the_url_variable_is_not_overridden_by_a_prefixed_one(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://real:6379/0")
    monkeypatch.setenv("SCRAPER_REDIS_URL", "redis://ignored:6379/0")

    assert RunnerSettings.from_env().redis_url == "redis://real:6379/0"
