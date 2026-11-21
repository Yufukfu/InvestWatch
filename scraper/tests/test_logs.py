import io
import json
import logging

from iw_scraper.logs import JsonFormatter, configure_logging


def lines(stream: io.StringIO) -> list[str]:
    return [line for line in stream.getvalue().split("\n") if line]


def test_every_record_is_one_line_of_json_with_the_basic_fields():
    stream = io.StringIO()
    configure_logging(stream)

    logging.getLogger("iw_scraper.jobs").warning("lock lost for %s", "src-1")

    [line] = lines(stream)
    record = json.loads(line)
    assert (record["level"], record["logger"], record["message"]) == ("WARNING", "iw_scraper.jobs", "lock lost for src-1")
    assert record["ts"].endswith("Z")


def test_a_multi_line_message_and_a_traceback_stay_on_one_line():
    stream = io.StringIO()
    configure_logging(stream)
    log = logging.getLogger("iw_scraper.test")

    try:
        raise ValueError("boom")
    except ValueError:
        log.exception("first line\nsecond line")

    [line] = lines(stream)
    record = json.loads(line)
    assert record["message"] == "first line\nsecond line"
    assert "ValueError: boom" in record["exception"]


def test_configuring_twice_does_not_duplicate_lines():
    stream = io.StringIO()
    configure_logging(stream)
    configure_logging(stream)

    logging.getLogger("x").info("once")

    assert len(lines(stream)) == 1


def test_third_party_loggers_are_formatted_too():
    stream = io.StringIO()
    configure_logging(stream)

    logging.getLogger("arq.worker").info("job started")

    assert json.loads(lines(stream)[0])["logger"] == "arq.worker"


def test_url_credentials_are_redacted_in_messages_and_tracebacks():
    stream = io.StringIO()
    configure_logging(stream)
    log = logging.getLogger("iw_scraper.fetch")

    try:
        raise ConnectionError("cannot reach http://scraper:hunter2@proxy.local:8080/path")
    except ConnectionError:
        log.exception("proxy http://scraper:hunter2@proxy.local:8080 failed")

    [line] = lines(stream)
    assert "hunter2" not in line
    assert "http://***@proxy.local:8080" in json.loads(line)["message"]


def test_a_log_call_with_bad_arguments_still_produces_a_line():
    record = logging.LogRecord("x", logging.WARNING, __file__, 1, "needs two: %s %s", ("only-one",), None)

    line = JsonFormatter().format(record)

    assert "unformattable" in json.loads(line)["message"]


def test_records_below_the_level_are_dropped():
    stream = io.StringIO()
    configure_logging(stream, level=logging.WARNING)

    logging.getLogger("x").info("quiet")
    logging.getLogger("x").warning("loud")

    assert [json.loads(line)["message"] for line in lines(stream)] == ["loud"]
