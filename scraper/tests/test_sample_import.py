"""Sample import, pure logic: readers, directory scan and manifest. The ingest run is covered further down."""

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from iw_scraper.parsing import ParseFailure, parse_page
from iw_scraper.sample_import import ManifestError, load_manifest, read_sample, scan
from iw_scraper.types import Reason

PAGE = (
    '<html><head><title>Oferta</title><meta name="author" content="Jan"></head>'
    '<body><p>Zysk 20% miesiecznie</p><a href="https://example.com/a">a</a></body></html>'
)
MAX_BYTES = 1000


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    directory = tmp_path / "uknf-1"
    directory.mkdir()
    return directory


def put(directory: Path, name: str, content: str | bytes) -> None:
    path = directory / name
    path.write_bytes(content.encode() if isinstance(content, str) else content)


def read(directory: Path, name: str, *, manifest: str | None = None, max_bytes: int = MAX_BYTES):
    if manifest is not None:
        put(directory, "samples.toml", manifest)
    sample_set = load_manifest(directory, kind="third_party", modules="M3")
    return read_sample(directory, name, sample_set.settings_for(name), max_bytes)


def test_an_html_sample_gives_what_parse_page_gives(directory):
    put(directory, "oferta.html", PAGE)

    page, author = read(directory, "oferta.html")

    url = "https://sample.invalid/uknf-1/oferta.html"
    parsed = parse_page(PAGE.encode(), "text/html", url)
    assert (page["text"], page["title"], page["canonical_url"]) == ("Zysk 20% miesiecznie a", "Oferta", url)
    assert (page["text"], page["title"], page["canonical_url"]) == (parsed.text, parsed.title, parsed.canonical_url)
    assert page["links"] == [{"href": "https://example.com/a"}]
    assert page["url"] == url and page["html"] == PAGE
    assert page["scrape_meta"] == {"client": "sample-import", "sample_file": "oferta.html"}
    assert author is None


@pytest.mark.parametrize("name", ["post.txt", "post.md", "POST.TXT"])
def test_a_text_sample_becomes_text_with_a_non_blank_html(directory, name):
    put(directory, name, "Kup teraz\n a < b")

    page, _ = read(directory, name)

    assert page["text"] == "Kup teraz\n a < b"
    assert page["html"] == "<pre>Kup teraz\n a &lt; b</pre>"
    assert page["links"] == [] and page["title"] is None


def test_a_file_name_is_quoted_in_the_default_url(directory):
    put(directory, "moja oferta.txt", "tekst")

    page, _ = read(directory, "moja oferta.txt")

    assert page["url"] == "https://sample.invalid/uknf-1/moja%20oferta.txt"


def test_scan_lists_supported_files_and_reports_the_rest_as_skipped(directory, tmp_path):
    put(directory, "a.html", PAGE)
    put(directory, "b.txt", "x")
    put(directory, "skan.pdf", "%PDF")
    put(directory, "samples.toml", "")
    put(directory, ".DS_Store", "finder noise")
    (directory / ".hidden.txt").symlink_to(directory / "a.html")
    (directory / "nested").mkdir()
    put(directory / "nested", "deep.txt", "never read")

    entries = {entry.name: entry.skipped for entry in scan(directory)}

    assert entries == {"a.html": None, "b.txt": None, "skan.pdf": "unsupported"}


def test_scan_skips_a_symlink_instead_of_following_it(directory, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("do not read")
    (directory / "x.txt").symlink_to(outside)

    assert {entry.name: entry.skipped for entry in scan(directory)} == {"x.txt": "symlink"}


def test_reading_refuses_a_symlink_even_if_scan_was_raced(directory, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("do not read")
    (directory / "x.txt").symlink_to(outside)

    with pytest.raises(ParseFailure) as failure:
        read(directory, "x.txt")

    assert failure.value.reason is Reason.PARSE_ERROR and "do not read" not in failure.value.detail


def test_an_oversized_file_is_a_parse_error_naming_only_the_file(directory):
    put(directory, "big.txt", "x" * (MAX_BYTES + 1))

    with pytest.raises(ParseFailure) as failure:
        read(directory, "big.txt")

    assert failure.value.reason is Reason.PARSE_ERROR
    assert str(directory) not in failure.value.detail and "big.txt" in failure.value.detail


def test_a_file_that_grew_after_the_size_check_is_still_refused(directory, monkeypatch):
    put(directory, "grows.txt", "x" * (MAX_BYTES + 50))
    real_fstat = os.fstat

    def small_when_checked(fd):  # what a file looks like that is appended to between fstat and read
        info = real_fstat(fd)
        return os.stat_result((info.st_mode, info.st_ino, info.st_dev, 1, 0, 0, 10, 0, 0, 0))

    monkeypatch.setattr(os, "fstat", small_when_checked)

    with pytest.raises(ParseFailure) as failure:
        read(directory, "grows.txt")

    assert failure.value.reason is Reason.PARSE_ERROR and "grows.txt" in failure.value.detail


def test_a_file_of_exactly_the_cap_is_read(directory):
    put(directory, "edge.txt", "x" * MAX_BYTES)

    page, _ = read(directory, "edge.txt")

    assert len(page["text"]) == MAX_BYTES


@pytest.mark.parametrize("content", [b"\xff\xfe\x00bad", b"has \x00 nul"])
def test_a_text_file_that_is_not_text_is_a_parse_error(directory, content):
    put(directory, "bad.txt", content)

    with pytest.raises(ParseFailure) as failure:
        read(directory, "bad.txt")

    assert failure.value.reason is Reason.PARSE_ERROR


def test_an_html_file_without_text_fails_with_the_parsers_reason(directory):
    put(directory, "empty.html", "<html><body></body></html>")

    with pytest.raises(ParseFailure) as failure:
        read(directory, "empty.html")

    assert failure.value.reason is Reason.EMPTY_TEXT


def test_a_per_file_value_wins_over_the_set_default(directory):
    manifest = """
source_kind = "third_party"
target_modules = ["M3"]
lang = "pl"

[files."xtb.html"]
source_kind = "firm_own"
target_modules = ["M2", "M3"]
platform = "forum"
lang = "en"
title = "XTB oferta"
url = "https://example.com/xtb"
"""
    put(directory, "xtb.html", PAGE)
    put(directory, "other.html", PAGE)
    put(directory, "samples.toml", manifest)

    sample_set = load_manifest(directory)
    xtb, other = sample_set.settings_for("xtb.html"), sample_set.settings_for("other.html")
    page, _ = read_sample(directory, "xtb.html", xtb, MAX_BYTES)

    assert (xtb.source_kind, xtb.platform, xtb.target_modules) == ("firm_own", "forum", ("M2", "M3"))
    assert (other.source_kind, other.platform, other.target_modules) == ("third_party", "web", ("M3",))
    assert (page["title"], page["lang"], page["url"], page["canonical_url"]) == (
        "XTB oferta", "en", "https://example.com/xtb", "https://example.com/xtb",
    )
    assert read_sample(directory, "other.html", other, MAX_BYTES)[0]["lang"] == "pl"


def test_the_flags_stand_in_for_a_manifest_and_the_manifest_wins(directory):
    put(directory, "a.txt", "x")
    assert load_manifest(directory, kind="unknown", modules="M1,M3").settings_for("a.txt").target_modules == ("M1", "M3")

    put(directory, "samples.toml", 'source_kind = "firm_own"\ntarget_modules = ["M2"]\n')
    settings = load_manifest(directory, kind="unknown", modules="M1").settings_for("a.txt")

    assert (settings.source_kind, settings.target_modules) == ("firm_own", ("M2",))


def test_the_set_name_and_url_come_from_the_manifest_or_the_directory(directory):
    put(directory, "a.txt", "x")
    plain = load_manifest(directory, kind="unknown", modules="M1")
    put(directory, "samples.toml", 'name = "Próbki UKNF"\nurl = "https://example.com/set"\nsource_kind = "unknown"\ntarget_modules = ["M1"]\n')
    named = load_manifest(directory)

    assert (plain.name, plain.url) == ("uknf-1", "https://sample.invalid/uknf-1")
    assert (named.name, named.url) == ("Próbki UKNF", "https://example.com/set")


def test_a_directory_name_with_spaces_and_polish_letters_gives_a_valid_url(tmp_path):
    directory = tmp_path / "Próbki UKNF 1"
    directory.mkdir()
    put(directory, "a.txt", "x")

    sample_set = load_manifest(directory, kind="unknown", modules="M1")

    assert sample_set.url == "https://sample.invalid/pr-bki-uknf-1"
    assert sample_set.settings_for("a.txt").url == "https://sample.invalid/pr-bki-uknf-1/a.txt"


@pytest.mark.parametrize(
    ("manifest", "key"),
    [
        ('source_kind = "bank"\ntarget_modules = ["M3"]', "source_kind"),
        ('source_kind = "unknown"\ntarget_modules = ["M4"]', "target_modules"),
        ('source_kind = "unknown"\ntarget_modules = []', "target_modules"),
        ('source_kind = "unknown"\ntarget_modules = ["M3"]\nplatform = "tv"', "platform"),
        ('source_kind = "unknown"\ntarget_modules = ["M3"]\nlang = "PL"', "lang"),
        ('source_kind = "unknown"\ntarget_modules = ["M3"]\nlang = "pol"', "lang"),
        ('source_kind = "unknown"\ntarget_modules = ["M3"]\npublished_at = "yesterday"', "published_at"),
        ('source_kind = "unknown"\ntarget_modules = ["M3"]\npublished_at = "2026-11-01T10:00:00"', "published_at"),
        ('source_kind = "unknown"\ntarget_modules = ["M3"]\nauthor = { name = "X", rank = 1 }', "author"),
        ('source_kind = "unknown"\ntarget_modules = ["M3"]\nauthor = { profile_url = "javascript:alert(1)" }', "author"),
        ('source_kind = "unknown"\ntarget_modules = ["M3"]\nurl = "ftp://example.com"', "url"),
        ('source_kind = "unknown"\ntarget_modules = ["M3"]\ncolour = "red"', "colour"),
        ('source_kind = "unknown"\ntarget_modules = ["M3"]\n[files."a.txt"]\nname = "x"', "name"),
        ('source_kind = "unknown"\ntarget_modules = ["M3"]\n[files."a.txt"]\nurl = "javascript:alert(1)"', "url"),
        ('source_kind = "unknown"\ntarget_modules = ["M3"]\n[files."a.txt"]\nsource_kind = "bank"', "source_kind"),
        ('source_kind = "unknown"\ntarget_modules = ["M3"]\n[files."gone.txt"]\nlang = "pl"', "gone.txt"),
        ('target_modules = ["M3"]', "source_kind"),
        ('source_kind = "unknown"', "target_modules"),
        ("source_kind = ", "samples.toml"),
    ],
)
def test_an_invalid_manifest_is_refused_and_names_the_key(directory, manifest, key):
    put(directory, "a.txt", "x")
    put(directory, "samples.toml", manifest)

    with pytest.raises(ManifestError, match=key):
        load_manifest(directory)


def test_without_a_manifest_the_routing_flags_are_required(directory):
    put(directory, "a.txt", "x")

    with pytest.raises(ManifestError, match="--kind"):
        load_manifest(directory, kind=None, modules="M3")
    with pytest.raises(ManifestError, match="--modules"):
        load_manifest(directory, kind="unknown", modules=None)
    with pytest.raises(ManifestError, match="target_modules"):
        load_manifest(directory, kind="unknown", modules="M9")


def test_the_author_comes_only_from_the_manifest(directory):
    manifest = """
source_kind = "firm_own"
target_modules = ["M2"]

[files."with.html"]
author = { name = "X", handle = "@x", profile_url = "https://example.com/x" }
"""
    put(directory, "with.html", PAGE)
    put(directory, "without.html", PAGE)  # carries <meta name="author" content="Jan">

    _, declared = read(directory, "with.html", manifest=manifest)
    page, markup_only = read(directory, "without.html")

    assert declared == {"name": "X", "handle": "@x", "profile_url": "https://example.com/x"}
    assert markup_only is None and "author" not in page


def test_published_at_is_normalised_to_utc(directory):
    manifest = """
source_kind = "unknown"
target_modules = ["M1"]

[files."a.txt"]
published_at = 2026-11-01T10:00:00Z

[files."b.txt"]
published_at = "2026-11-01T12:00:00+02:00"
"""
    put(directory, "a.txt", "x")
    put(directory, "b.txt", "y")

    first, _ = read(directory, "a.txt", manifest=manifest)
    second, _ = read(directory, "b.txt")

    assert first["published_at"] == second["published_at"] == "2026-11-01T10:00:00Z"
    assert datetime.fromisoformat(first["published_at"].replace("Z", "+00:00")) == datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
