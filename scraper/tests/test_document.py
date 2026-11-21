import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from iw_scraper.config import contracts_dir
from iw_scraper.document import build_document
from iw_scraper.fetch import FetchResult
from iw_scraper.parsing import ParsedPage
from iw_scraper.types import Source

FETCHED = datetime(2026, 11, 21, 12, 30, 5, tzinfo=timezone.utc)


def source(kind: str = "firm_own", platform: str = "web") -> Source:
    return Source(
        id=str(uuid.uuid4()), name="KNF", platform=platform, url="https://example.pl/start", source_kind=kind,
        target_modules=("m1",), active=True,
    )


def result(proxy_id: str | None = None, status: int = 200) -> FetchResult:
    return FetchResult(
        url="https://www.example.pl/final", status=status, content_type="text/html; charset=utf-8",
        body=b"<html></html>", headers={}, proxy_id=proxy_id,
    )


PAGE = ParsedPage(
    title="Akcje: ryzyko",
    canonical_url="https://www.example.pl/canonical",
    text="Treść strony z ostrzeżeniem.",
    links=("https://www.example.pl/kontakt", "https://other.example/x"),
)


def schema_errors(document: dict) -> list[str]:
    schema = json.loads((contracts_dir() / "schemas" / "scraped-document.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    full = {"id": str(uuid.uuid4()), **document}  # `id` and `content_hash` are added when the document is stored
    return [e.message for e in validator.iter_errors(full)]


def test_the_document_carries_the_fetch_and_parse_fields():
    document = build_document(source(), result(), PAGE, FETCHED)

    assert document["url"] == "https://www.example.pl/final"
    assert document["canonical_url"] == "https://www.example.pl/canonical"
    assert document["http_status"] == 200
    assert document["title"] == "Akcje: ryzyko"
    assert document["text"] == "Treść strony z ostrzeżeniem."
    assert document["links"] == [{"href": "https://www.example.pl/kontakt"}, {"href": "https://other.example/x"}]


def test_platform_source_kind_and_source_id_come_from_the_source_row_not_the_page():
    page = ParsedPage(title="third_party", canonical_url="https://x.example/", text="source_kind: third_party", links=())
    row = source("firm_own")

    document = build_document(row, result(), page, FETCHED)

    assert document["source_kind"] == "firm_own"
    assert document["platform"] == "web"
    assert document["source_id"] == row.id


def test_status_and_platform_are_copied_not_assumed():
    document = build_document(source(platform="forum"), result(status=203), PAGE, FETCHED)

    assert document["http_status"] == 203
    assert document["platform"] == "forum"


def test_fetched_at_is_utc_whatever_zone_the_clock_gave():
    plus_two = timezone(timedelta(hours=2))

    document = build_document(source(), result(), PAGE, FETCHED.astimezone(plus_two))

    assert document["fetched_at"] == "2026-11-21T12:30:05+00:00"


def test_a_naive_fetch_time_is_refused():
    with pytest.raises(ValueError, match="timezone"):
        build_document(source(), result(), PAGE, datetime(2026, 11, 21, 12, 30, 5))


def test_scrape_meta_names_the_client_and_holds_a_proxy_identifier_never_a_url():
    document = build_document(source(), result("proxy-1a2b3c4d"), PAGE, FETCHED)

    assert document["scrape_meta"] == {"scraper": "httpx", "client": "noble-tls", "proxy": "proxy-1a2b3c4d"}


def test_a_direct_request_has_a_null_proxy():
    assert build_document(source(), result(None), PAGE, FETCHED)["scrape_meta"]["proxy"] is None


def test_the_document_conforms_to_the_contract_schema():
    assert schema_errors(build_document(source(), result("proxy-1a2b3c4d"), PAGE, FETCHED)) == []
    assert schema_errors(build_document(source("unknown"), result(), ParsedPage(None, "https://x.example/", "t", ()), FETCHED)) == []


def test_a_page_without_title_stays_null_not_empty():
    page = ParsedPage(title=None, canonical_url="https://x.example/", text="t", links=())

    assert build_document(source(), result(), page, FETCHED)["title"] is None
