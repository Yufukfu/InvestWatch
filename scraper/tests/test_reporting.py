import io
import json
import logging
from datetime import datetime

from iw_scraper.reporting import InMemorySink, json_logger, redact
from iw_scraper.types import JobError, Reason

PROXY = "http://user:secret@proxy.example:8080"


def test_redact_hides_credentials_in_a_url():
    assert redact(PROXY) == "http://***@proxy.example:8080"


def test_redact_hides_every_url_in_a_message():
    text = f"via {PROXY} then socks5://a:b@other:1080 failed"

    cleaned = redact(text)

    assert "secret" not in cleaned and ":b@" not in cleaned
    assert cleaned == "via http://***@proxy.example:8080 then socks5://***@other:1080 failed"


def test_redact_handles_an_at_sign_in_the_password():
    assert "ss" not in redact("http://user:p@ss@host:8080/x")


def test_redact_leaves_urls_without_credentials_alone():
    text = "GET https://www.knf.gov.pl/a?b=c@d failed"

    assert redact(text) == text


def test_sink_stores_the_error_with_credentials_removed():
    sink = InMemorySink()

    sink.record(JobError(reason=Reason.TIMEOUT, detail=f"timeout via {PROXY}", source_id="s1"))

    assert len(sink.errors) == 1
    stored = sink.errors[0]
    assert stored.reason is Reason.TIMEOUT
    assert stored.source_id == "s1"
    assert "secret" not in stored.detail
    assert stored.detail == "timeout via http://***@proxy.example:8080"


def _logged(emit) -> dict:
    stream = io.StringIO()
    emit(json_logger("iw_scraper.test", stream))
    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


def test_logger_writes_one_json_line_with_utc_timestamp():
    record = _logged(lambda log: log.info("fetched", extra={"status": 200}))

    assert record["message"] == "fetched"
    assert record["level"] == "INFO"
    assert record["logger"] == "iw_scraper.test"
    assert record["status"] == 200
    assert datetime.fromisoformat(record["ts"]).utcoffset().total_seconds() == 0


def test_logger_redacts_message_and_extra_fields():
    record = _logged(lambda log: log.error(f"failed via {PROXY}", extra={"proxy": PROXY}))

    assert "secret" not in json.dumps(record)
    assert record["proxy"] == "http://***@proxy.example:8080"


def test_logger_redacts_exception_text():
    def emit(log: logging.Logger) -> None:
        try:
            raise RuntimeError(f"connect {PROXY}")
        except RuntimeError:
            log.exception("boom")

    record = _logged(emit)

    assert "secret" not in json.dumps(record)
    assert "RuntimeError" in record["exc"]


def test_logger_is_not_duplicated_on_repeated_setup():
    stream = io.StringIO()
    json_logger("iw_scraper.dup", stream)
    log = json_logger("iw_scraper.dup", stream)

    log.info("once")

    assert len(stream.getvalue().splitlines()) == 1
