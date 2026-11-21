"""Building, validating and hashing a document (no services needed)."""

import hashlib
import uuid
from datetime import datetime, timezone

import pytest

from iw_scraper.ingest.document import build_document, content_hash, normalise_text
from iw_scraper.ingest.validate import check_document
from iw_scraper.types import Reason

FETCHED_AT = datetime(2026, 11, 21, 15, 0, 0, tzinfo=timezone.utc)
PAGE = {"url": "https://alfa.example.com/konto", "text": "Zysk do 20%", "title": "Konto", "html": "<p>x</p>"}


def build(source, page=PAGE, **kw):
    return build_document(page, source, fetched_at=FETCHED_AT, duration_ms=120, proxy="proxy-1", **kw)


def test_build_sets_contract_minimum_and_source_fields(source):
    doc = build(source)
    assert doc["platform"] == "web"
    assert doc["source_kind"] == "firm_own"
    assert doc["source_id"] == source.id
    assert doc["url"] == PAGE["url"]
    assert doc["text"] == "Zysk do 20%"
    assert doc["fetched_at"] == "2026-11-21T15:00:00Z"


def test_build_generates_uuid_v4_per_document(source):
    first, second = build(source), build(source)
    assert uuid.UUID(first["id"]).version == 4
    assert first["id"] != second["id"]


def test_build_records_scrape_meta_without_credentials(source):
    meta = build(source)["scrape_meta"]
    assert meta == {"scraper": "httpx", "duration_ms": 120, "proxy": "proxy-1"}


def test_build_does_not_store_raw_html_in_the_document(source):
    assert "html" not in build(source)


def test_build_drops_a_page_supplied_html_object_key(source):
    # only the pipeline sets it, after a real upload; a page must not point a row at an arbitrary object
    doc = build(source, {"url": PAGE["url"], "text": "Zysk", "html_object_key": "html/someone-elses.html"})
    assert "html_object_key" not in doc


def test_build_drops_a_page_supplied_author(source):
    # page markup (meta, rel=author, embedded JSON) is writer-controlled and analytics routes on author (issue 36)
    author = {"name": "Alfa", "handle": "@alfa", "profile_url": "https://alfa.example.com/"}
    doc = build(source, {**PAGE, "author": author})
    assert "author" not in doc
    assert check_document(doc) is None


def test_build_stores_an_author_the_collector_passes_explicitly(source):
    # the trusted path: a platform collector with account data, never the page dict
    account = {"name": "Kanał", "handle": "@kanal", "profile_url": "https://t.me/kanal", "followers": 10}
    doc = build(source, {**PAGE, "author": {"handle": "@firm"}}, author=account)
    assert doc["author"] == account
    assert check_document(doc) is None


def test_build_has_no_author_key_without_a_trusted_one(source):
    assert "author" not in build(source)


def test_build_does_not_mutate_the_page(source):
    page = dict(PAGE)
    build(source, page)
    assert page == PAGE


def test_valid_document_passes_schema(source):
    assert check_document(build(source)) is None


def test_missing_text_is_schema_invalid(source):
    page = {k: v for k, v in PAGE.items() if k != "text"}
    error = check_document(build(source, page))
    assert error is not None
    assert error.reason is Reason.SCHEMA_INVALID
    assert error.source_id == source.id


def test_malformed_fetched_at_is_schema_invalid(source):
    doc = build(source)
    doc["fetched_at"] = "yesterday"
    error = check_document(doc)
    assert error is not None and error.reason is Reason.SCHEMA_INVALID


@pytest.mark.parametrize("text", ["", "   \n\t "])
def test_blank_text_is_an_empty_text_error_not_a_document(source, text):
    error = check_document(build(source, {**PAGE, "text": text}))
    assert error is not None
    assert error.reason is Reason.EMPTY_TEXT
    assert error.source_id == source.id


def test_page_supplied_content_hash_never_survives_without_text(source):
    page = {"url": PAGE["url"], "content_hash": "a" * 64}
    assert "content_hash" not in build(source, page)


def test_document_without_source_id_is_rejected(source):
    doc = build(source)
    doc["source_id"] = None
    error = check_document(doc)
    assert error is not None and error.reason is Reason.SCHEMA_INVALID


def test_whitespace_only_difference_has_the_same_hash():
    expected = hashlib.sha256("Zysk do 20%".encode()).hexdigest()
    assert content_hash("Zysk  do 20%\n") == expected
    assert content_hash("Zysk do 20%") == expected


def test_case_difference_changes_the_hash():
    assert content_hash("Zysk do 20%") != content_hash("ZYSK DO 20%")


def test_nfc_equivalent_text_has_the_same_hash():
    assert content_hash("é") == content_hash("é")


@pytest.mark.parametrize("raw,expected", [("  a \t\n b  ", "a b"), ("", ""), (" x ", "x")])
def test_normalise_text(raw, expected):
    assert normalise_text(raw) == expected


def test_a_scrape_meta_key_the_page_supplied_survives_and_the_fetch_facts_are_added(source):
    meta = build(source, PAGE | {"scrape_meta": {"client": "chrome_146", "duration_ms": 1}})["scrape_meta"]
    assert meta == {"client": "chrome_146", "scraper": "httpx", "duration_ms": 120, "proxy": "proxy-1"}


def test_a_scraper_value_the_page_supplied_is_kept(source):
    assert build(source, PAGE | {"scrape_meta": {"scraper": "playwright"}})["scrape_meta"]["scraper"] == "playwright"


@pytest.mark.parametrize(
    "field,value",
    [
        ("url", "javascript:alert(1)"),
        ("canonical_url", "javascript:alert(1)"),
        ("canonical_url", "data:text/html,x"),
        ("author", {"name": "a", "profile_url": "javascript:alert(1)"}),
    ],
)
def test_a_non_web_url_scheme_is_schema_invalid(source, field, value):
    error = check_document(build(source) | {field: value})  # set after the build: a page cannot supply `author`
    assert error is not None and error.reason is Reason.SCHEMA_INVALID
    assert "http or https" in error.detail


# The one definition of `content_hash` (ADR 0105, `.docs/integration-plan.md` §3): NFC, whitespace collapsed and trimmed,
# case kept, UTF-8, sha256 hex. The hashes are literals, never computed with the code under test; the stored value feeds the
# unique dedup index on `documents`, so a change here would turn every stored hash into a miss.
@pytest.mark.parametrize(
    "text,folded,expected",
    [
        ("ﬁnanse", "finanse", "940eee0cfc77cf748d13d9ebbb2530ff252c93ff9fffdd3114f8b10329e8093a"),  # ligature fi
        ("m²", "m2", "09c2e207e28b877591a6d65a2e78637bea09fa49d68def18c0419b18ff47ae89"),  # superscript two
        ("１２３%", "123%", "359a698d899b204c2eab19f1b13a75f203816dd695e6620386819c67b1b62369"),  # full-width digits
    ],
)
def test_compatibility_characters_are_kept_not_folded(text, folded, expected):
    assert normalise_text(text) == text
    assert content_hash(text) == expected
    assert content_hash(text) != content_hash(folded)


def test_decomposed_and_composed_text_hash_to_the_literal():
    assert content_hash("é") == "4a99557e4033c3539de2eb65472017cad5f9557f7a0625a09f1c3f6e2ba69c4c"
    assert content_hash("é") == "4a99557e4033c3539de2eb65472017cad5f9557f7a0625a09f1c3f6e2ba69c4c"


def test_unicode_whitespace_collapses_to_one_space():
    assert normalise_text(" a 　\t b ") == "a b"
    assert content_hash(" a 　b ") == "c8687a08aa5d6ed2044328fa6a697ab8e96dc34291e8c2034ae8c38e6fcc6d65"
