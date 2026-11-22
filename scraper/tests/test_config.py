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


def test_the_worker_and_scheduler_intervals_are_configurable(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://x:6379/0")
    monkeypatch.setenv("SCRAPER_CLAIM_IDLE", "15")
    monkeypatch.setenv("SCRAPER_TICK_INTERVAL", "20")
    monkeypatch.setenv("SCRAPER_SWEEP_INTERVAL", "300.5")

    settings = RunnerSettings.from_env()

    assert (settings.claim_idle, settings.tick_interval, settings.sweep_interval) == (15.0, 20.0, 300.5)


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


def test_the_requeue_cap_is_configurable(monkeypatch):
    monkeypatch.setenv("SCRAPER_MAX_REQUEUES", "7")

    assert QueueSettings.from_env().max_requeues == 7


def test_the_queue_defaults_match_the_web_collection_spec(monkeypatch):
    for name in ("SCRAPER_FAILURE_THRESHOLD", "SCRAPER_DOMAIN_COOLDOWN", "SCRAPER_MAX_RETRY_AFTER"):
        monkeypatch.delenv(name, raising=False)

    settings = QueueSettings.from_env()

    assert (settings.failure_threshold, settings.domain_cooldown, settings.max_retry_after) == (5, 600.0, 300.0)


def test_social_max_posts_defaults_to_two_pages(monkeypatch):
    from iw_scraper.config import social_max_posts

    monkeypatch.delenv("SOCIAL_MAX_POSTS", raising=False)

    assert social_max_posts() == 40


def test_social_max_posts_is_read_as_a_whole_number(monkeypatch):
    from iw_scraper.config import social_max_posts

    monkeypatch.setenv("SOCIAL_MAX_POSTS", "60")

    assert social_max_posts() == 60


@pytest.mark.parametrize("value", ["0", "-5", "many", "2.5", ""])
def test_social_max_posts_refuses_anything_else(monkeypatch, value):
    from iw_scraper.config import social_max_posts

    monkeypatch.setenv("SOCIAL_MAX_POSTS", value)

    with pytest.raises(ValueError, match="SOCIAL_MAX_POSTS"):
        social_max_posts()


def test_youtube_max_videos_defaults_to_ten(monkeypatch):
    from iw_scraper.config import youtube_max_videos

    monkeypatch.delenv("YOUTUBE_MAX_VIDEOS", raising=False)

    assert youtube_max_videos() == 10


def test_youtube_max_videos_is_read_as_a_whole_number(monkeypatch):
    from iw_scraper.config import youtube_max_videos

    monkeypatch.setenv("YOUTUBE_MAX_VIDEOS", "3")

    assert youtube_max_videos() == 3


@pytest.mark.parametrize("value", ["0", "-5", "many", "2.5", ""])
def test_youtube_max_videos_refuses_anything_else(monkeypatch, value):
    from iw_scraper.config import youtube_max_videos

    monkeypatch.setenv("YOUTUBE_MAX_VIDEOS", value)

    with pytest.raises(ValueError, match="YOUTUBE_MAX_VIDEOS"):
        youtube_max_videos()


@pytest.mark.parametrize("value", [None, "", "   "])
def test_an_unset_or_empty_transcript_proxy_means_transcripts_are_off(monkeypatch, value):
    from iw_scraper.config import yt_transcript_proxy

    monkeypatch.delenv("YT_TRANSCRIPT_PROXY", raising=False)
    if value is not None:
        monkeypatch.setenv("YT_TRANSCRIPT_PROXY", value)

    assert yt_transcript_proxy() is None


def test_a_transcript_proxy_is_an_http_url(monkeypatch):
    from iw_scraper.config import yt_transcript_proxy

    monkeypatch.setenv("YT_TRANSCRIPT_PROXY", "http://user:pa55word@resi.example:8080")

    assert yt_transcript_proxy() == "http://user:pa55word@resi.example:8080"


@pytest.mark.parametrize("value", ["socks5://user:pa55word@resi.example:1080", "user:pa55word@resi.example:8080", "http://"])
def test_a_bad_transcript_proxy_names_the_variable_and_never_echoes_it(monkeypatch, value):
    from iw_scraper.config import yt_transcript_proxy

    monkeypatch.setenv("YT_TRANSCRIPT_PROXY", value)

    with pytest.raises(ValueError, match="YT_TRANSCRIPT_PROXY") as error:
        yt_transcript_proxy()

    assert "pa55word" not in str(error.value) and "resi.example" not in str(error.value)
    assert error.value.__cause__ is None and error.value.__suppress_context__


def test_x_cookies_are_both_values_when_both_are_set(monkeypatch):
    from iw_scraper.config import x_cookies

    monkeypatch.setenv("X_AUTH_TOKEN", " tok-123 ")
    monkeypatch.setenv("X_CT0", "ct0-456")

    assert x_cookies() == ("tok-123", "ct0-456")


@pytest.mark.parametrize(
    "auth, ct0", [(None, "ct0-456"), ("tok-123", None), ("", "ct0-456"), ("tok-123", "  ")]
)
def test_x_cookies_are_none_when_either_is_missing_or_empty(monkeypatch, auth, ct0):
    from iw_scraper.config import x_cookies

    for name, value in (("X_AUTH_TOKEN", auth), ("X_CT0", ct0)):
        monkeypatch.delenv(name, raising=False)
        if value is not None:
            monkeypatch.setenv(name, value)

    assert x_cookies() is None
