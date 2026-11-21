from pathlib import Path

import pytest
from jsonschema import FormatChecker

from iw_scraper.parsing import ParsedPage, ParseFailure, ParserRegistry, parse_page, to_uri
from iw_scraper.types import Reason

FIXTURES = Path(__file__).parent / "fixtures"
HTML = "text/html; charset=utf-8"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# Built here, not stored: a raw non-UTF-8 file in the repo trips the secret-scan hook's awk.
WINDOWS_1250_PAGE = (
    '<!doctype html><html><head><meta http-equiv="Content-Type" content="text/html; charset=windows-1250">'
    "<title>Żółć</title></head><body><p>Zażółć gęślą jaźń: żółć</p></body></html>"
).encode("cp1250")
MALFORMED_PAGE = b"\x00\x01\x02 not html \xff\xfe"


def test_article_title_text_and_relative_link():
    page = parse_page(load("article.html"), HTML, "https://example.pl/artykul")

    assert page.title == "Akcje: ryzyko"
    assert "Inwestowanie w akcje niesie ryzyko." in page.text
    assert "https://example.pl/kontakt" in page.links


def test_script_and_style_content_is_not_text():
    page = parse_page(load("article.html"), HTML, "https://example.pl/")

    assert "secret" not in page.text
    assert "color:red" not in page.text


def test_canonical_resolved_against_final_url():
    page = parse_page(load("article.html"), HTML, "https://example.pl/artykul?utm=1")

    assert page.canonical_url == "https://example.pl/artykul/akcje-ryzyko"


def test_title_falls_back_to_h1_and_canonical_to_final_url():
    page = parse_page(load("no_title.html"), HTML, "https://example.pl/a")

    assert page.title == "Ostrzeżenie publiczne"
    assert page.canonical_url == "https://example.pl/a"


def test_non_navigational_links_are_dropped():
    page = parse_page(load("article.html"), HTML, "https://example.pl/")

    assert page.links == ("https://example.pl/kontakt", "https://example.pl/x#frag")


def test_markup_like_text_is_stored_verbatim():
    page = parse_page(load("article.html"), HTML, "https://example.pl/")

    assert "{{ 7*7 }}" in page.text
    assert "49" not in page.text


def test_windows_1250_from_meta_keeps_polish_letters():
    page = parse_page(WINDOWS_1250_PAGE, "text/html", "https://example.pl/")

    assert "żółć" in page.text
    assert page.title == "Żółć"


def test_windows_1250_from_header_keeps_polish_letters():
    body = "<html><body><p>żółć</p></body></html>".encode("cp1250")

    page = parse_page(body, "text/html; charset=windows-1250", "https://example.pl/")

    assert "żółć" in page.text


def test_saved_knf_page():
    page = parse_page(
        load("knf_warnings.html"), HTML, "https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne"
    )

    assert len(page.text) > 100_000
    assert page.title
    assert page.canonical_url.startswith("https://")


def test_empty_page_is_empty_text():
    with pytest.raises(ParseFailure) as err:
        parse_page(load("empty.html"), HTML, "https://example.pl/")

    assert err.value.reason is Reason.EMPTY_TEXT


def test_page_with_only_script_is_empty_text():
    with pytest.raises(ParseFailure) as err:
        parse_page(load("no_text.html"), HTML, "https://example.pl/")

    assert err.value.reason is Reason.EMPTY_TEXT


def test_unprocessable_markup_is_parse_error():
    with pytest.raises(ParseFailure) as err:
        parse_page(MALFORMED_PAGE, HTML, "https://example.pl/")

    assert err.value.reason is Reason.PARSE_ERROR


def test_non_html_content_type_is_parse_error():
    with pytest.raises(ParseFailure) as err:
        parse_page(b"%PDF-1.4", "application/pdf", "https://example.pl/a.pdf")

    assert err.value.reason is Reason.PARSE_ERROR


def _marker_parser(marker: str):
    def parser(body: bytes, content_type: str | None, final_url: str) -> ParsedPage:
        return ParsedPage(title=marker, canonical_url=final_url, text=marker, links=())

    return parser


def test_registered_parser_is_used_for_its_host():
    registry = ParserRegistry(default=_marker_parser("generic"))
    registry.register("example.pl", _marker_parser("site"))

    page = registry.parse(b"<p>x</p>", HTML, "https://example.pl/a")

    assert page.title == "site"


def test_host_without_parser_uses_the_generic_one():
    registry = ParserRegistry(default=_marker_parser("generic"))
    registry.register("example.pl", _marker_parser("site"))

    page = registry.parse(b"<p>x</p>", HTML, "https://other.pl/a")

    assert page.title == "generic"


def test_registry_default_is_the_real_generic_parser():
    page = ParserRegistry().parse(load("article.html"), HTML, "https://example.pl/")

    assert page.title == "Akcje: ryzyko"


def test_host_match_ignores_case_and_port():
    registry = ParserRegistry(default=_marker_parser("generic"))
    registry.register("Example.PL", _marker_parser("site"))

    page = registry.parse(b"<p>x</p>", HTML, "https://EXAMPLE.pl:8443/a")

    assert page.title == "site"


def test_registering_a_host_twice_is_refused():
    registry = ParserRegistry()
    registry.register("example.pl", _marker_parser("one"))

    with pytest.raises(ValueError):
        registry.register("example.pl", _marker_parser("two"))


def test_non_http_canonical_falls_back_to_final_url():
    body = b'<html><head><link rel="canonical" href="javascript:alert(1)"></head><body>x</body></html>'

    page = parse_page(body, HTML, "https://example.pl/a")

    assert page.canonical_url == "https://example.pl/a"


def test_text_after_a_script_is_kept():
    body = b"<html><body><p>before</p><script>x=1</script>after the script</body></html>"

    page = parse_page(body, HTML, "https://example.pl/")

    assert page.text == "before after the script"


def test_unparseable_link_is_dropped_not_fatal():
    body = b'<html><body>x<a href="http://[">bad</a><a href="/ok">ok</a></body></html>'

    page = parse_page(body, HTML, "https://example.pl/")

    assert page.links == ("https://example.pl/ok",)


def test_unparseable_canonical_falls_back_to_final_url():
    body = b'<html><head><link rel="canonical" href="http://["></head><body>x</body></html>'

    page = parse_page(body, HTML, "https://example.pl/a")

    assert page.canonical_url == "https://example.pl/a"


def test_a_canonical_with_non_ascii_characters_and_a_space_is_a_valid_uri():
    body = '<html><head><link rel="canonical" href="/ostrzeżenia lista"></head><body>x</body></html>'.encode()

    page = parse_page(body, HTML, "https://www.knf.gov.pl/a")

    assert page.canonical_url == "https://www.knf.gov.pl/ostrze%C5%BCenia%20lista"
    FormatChecker().check(page.canonical_url, "uri")  # raises when the contract's `format: uri` would refuse it


def test_links_are_percent_encoded_once_and_existing_escapes_stay():
    body = '<a href="/a%20b/ż?q=1&r=%C5%BC#f">x</a><p>x</p>'.encode()

    page = parse_page(body, HTML, "https://example.pl/")

    assert page.links == ("https://example.pl/a%20b/%C5%BC?q=1&r=%C5%BC#f",)


def test_a_parser_registered_for_the_bare_host_serves_the_www_host_and_back():
    registry = ParserRegistry(default=_marker_parser("generic"))
    registry.register("knf.gov.pl", _marker_parser("site"))

    assert registry.parse(b"<p>x</p>", HTML, "https://www.knf.gov.pl/a").title == "site"
    with pytest.raises(ValueError):
        registry.register("www.knf.gov.pl", _marker_parser("again"))


def test_a_non_ascii_host_goes_out_in_punycode_with_its_port_and_userinfo_kept():
    assert to_uri("https://zażółć.pl:8443/a b") == "https://xn--za-6ja4f8n1l.pl:8443/a%20b"
    assert to_uri("https://[::1]:80/ż") == "https://[::1]:80/%C5%BC"
    assert to_uri("https://u:p@zażółć.pl/x") == "https://u:p@xn--za-6ja4f8n1l.pl/x"


def test_a_link_to_a_non_ascii_host_keeps_a_host_the_guard_can_resolve():
    body = '<a href="https://zażółć.pl/a">x</a><p>x</p>'.encode()

    page = parse_page(body, HTML, "https://example.pl/")

    assert page.links == ("https://xn--za-6ja4f8n1l.pl/a",)


def test_a_stray_percent_is_escaped_and_a_real_escape_is_not():
    assert to_uri("https://example.pl/50%") == "https://example.pl/50%25"
    assert to_uri("https://example.pl/a%20b%2") == "https://example.pl/a%20b%252"


@pytest.mark.parametrize("url", ["http://[", "https://ż..pl/x", f"https://{'ż' * 64}.pl/"])
def test_a_url_that_cannot_be_encoded_comes_back_unchanged(url):
    assert to_uri(url) == url
