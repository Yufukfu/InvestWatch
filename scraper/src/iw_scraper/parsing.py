"""Generic HTML parser: bytes and headers in, contract fields out, or a `ParseFailure`."""

from collections.abc import Callable
from dataclasses import dataclass
from email.message import Message
from urllib.parse import urljoin, urlsplit

from lxml import etree, html

from iw_scraper.types import Reason

HTML_TYPES = {"text/html", "application/xhtml+xml"}
_SKIPPED_TAGS = ("script", "style", "noscript", "template")
_WEB_SCHEMES = {"http", "https"}


class ParseFailure(Exception):
    """The page cannot become a document; `reason` is a `Reason` from the closed set."""

    def __init__(self, reason: Reason, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class ParsedPage:
    title: str | None
    canonical_url: str
    text: str
    links: tuple[str, ...]


def content_type_params(content_type: str | None) -> tuple[str | None, str | None]:
    """(media type, charset) from a `Content-Type` header value."""
    if not content_type:
        return None, None
    message = Message()
    message["content-type"] = content_type
    return message.get_content_type(), message.get_content_charset()


def _build_tree(body: bytes, charset: str | None) -> html.HtmlElement:
    if b"\x00" in body:
        raise ParseFailure(Reason.PARSE_ERROR, "body contains NUL bytes, not markup")
    try:
        try:
            parser = html.HTMLParser(encoding=charset) if charset else html.HTMLParser()
        except LookupError:
            # an unknown header charset must not hide a usable <meta> declaration
            parser = html.HTMLParser()
        return html.document_fromstring(body, parser=parser)
    except (etree.ParserError, etree.XMLSyntaxError, ValueError) as exc:
        raise ParseFailure(Reason.PARSE_ERROR, f"markup not processable: {type(exc).__name__}") from exc


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _title(root: html.HtmlElement) -> str | None:
    for xpath in ("//title", "//h1"):
        for element in root.xpath(xpath):
            text = _collapse(element.text_content())
            if text:
                return text
    return None


def _web_url(base: str, href: str) -> str | None:
    """`href` resolved against `base` if it is an http(s) URL; None for anything else or a hostile value."""
    try:
        resolved = urljoin(base, href)
        return resolved if urlsplit(resolved).scheme in _WEB_SCHEMES else None
    except ValueError:  # e.g. `http://[` raises "Invalid IPv6 URL"; one bad value must not fail the page
        return None


def _canonical(root: html.HtmlElement, final_url: str) -> str:
    for link in root.xpath("//link[@rel and @href]"):
        if "canonical" in link.get("rel", "").lower().split():
            resolved = _web_url(final_url, link.get("href").strip())
            if resolved:
                return resolved
    return final_url


def _links(root: html.HtmlElement, final_url: str) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for anchor in root.xpath("//a[@href]"):
        href = anchor.get("href").strip()
        if not href or href.startswith("#"):
            continue
        resolved = _web_url(final_url, href)
        if resolved:
            seen.setdefault(resolved)
    return tuple(seen)


def _text(root: html.HtmlElement) -> str:
    # with_tail=False keeps the text that follows a removed element
    etree.strip_elements(root, *_SKIPPED_TAGS, with_tail=False)
    # the <title> is a field of its own, not page text
    body = root.find("body")
    # join text nodes with a space: text_content() would glue "<p>a</p><p>b</p>" into "ab"
    return _collapse(" ".join((body if body is not None else root).itertext()))


def parse_page(body: bytes, content_type: str | None, final_url: str) -> ParsedPage:
    """Parse one fetched page. Raises `ParseFailure` with `parse_error` or `empty_text`."""
    media_type, charset = content_type_params(content_type)
    if media_type is not None and media_type not in HTML_TYPES:
        raise ParseFailure(Reason.PARSE_ERROR, f"not an HTML response: {media_type}")

    root = _build_tree(body, charset)
    page_title = _title(root)
    canonical = _canonical(root, final_url)
    links = _links(root, final_url)
    text = _text(root)
    if not text:
        raise ParseFailure(Reason.EMPTY_TEXT, "page has no extractable text")
    return ParsedPage(title=page_title, canonical_url=canonical, text=text, links=links)


PageParser = Callable[[bytes, str | None, str], ParsedPage]


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


class ParserRegistry:
    """Parsers keyed by host; a host with no parser uses `default` (the generic parser)."""

    def __init__(self, default: PageParser = parse_page) -> None:
        self._default = default
        self._by_host: dict[str, PageParser] = {}

    def register(self, host: str, parser: PageParser) -> None:
        key = host.lower()
        if key in self._by_host:
            raise ValueError(f"a parser is already registered for {key}")
        self._by_host[key] = parser

    def parse(self, body: bytes, content_type: str | None, final_url: str) -> ParsedPage:
        return self._by_host.get(_host(final_url), self._default)(body, content_type, final_url)
