"""Telegram public channel preview (`https://t.me/s/<handle>`): one page in, a `Channel` out."""

import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlsplit

from lxml import etree, html

from iw_scraper.parsing import ParseFailure
from iw_scraper.social.model import Channel, Link, Post
from iw_scraper.types import Reason

_MULTIPLIERS = {"K": 1_000, "M": 1_000_000}
_COUNT = re.compile(r"^(\d+(?:\.\d+)?)([KM])?$", re.IGNORECASE)
_WEB_SCHEMES = {"http", "https"}
NETWORK = "telegram"
_CHANNEL_URL = re.compile(r"^https://t\.me/s/[A-Za-z0-9_]{5,32}$")


def valid_url(url: str) -> bool:
    """`https://t.me/s/<handle>`, the handle 5 to 32 letters, digits or underscores."""
    return _CHANNEL_URL.fullmatch(url) is not None


def _has_class(name: str) -> str:
    return f"contains(concat(' ', normalize-space(@class), ' '), ' {name} ')"


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _first_text(root: html.HtmlElement, class_name: str) -> str | None:
    for element in root.xpath(f"//*[{_has_class(class_name)}]"):
        text = _collapse(element.text_content())
        if text:
            return text
    return None


def _count(raw: str) -> int | None:
    """`36.1K` is 36100, `1.2M` is 1200000, `387` is 387; anything else is None."""
    match = _COUNT.match("".join(raw.split()))
    if not match:
        return None
    try:
        return int((Decimal(match.group(1)) * _MULTIPLIERS.get((match.group(2) or "").upper(), 1)).to_integral_value())
    except InvalidOperation:
        return None


def _followers(root: html.HtmlElement) -> int | None:
    for counter in root.xpath(f"//*[{_has_class('tgme_channel_info_counter')}]"):
        kind = _collapse(" ".join(counter.xpath(f".//*[{_has_class('counter_type')}]//text()")))
        if kind.lower().startswith("subscriber"):
            return _count(" ".join(counter.xpath(f".//*[{_has_class('counter_value')}]//text()")))
    return None


def _links(text_element: html.HtmlElement, base: str) -> tuple[Link, ...]:
    found: dict[str, Link] = {}
    for anchor in text_element.xpath(".//a[@href]"):
        href = urljoin(base, anchor.get("href").strip())
        if urlsplit(href).scheme in _WEB_SCHEMES:
            found.setdefault(href, Link(href, _collapse(anchor.text_content())))
    return tuple(found.values())


def _post(wrap: html.HtmlElement, base: str) -> tuple[Post | None, bool]:
    """(the post, True) when the wrapper holds a post; the post is None when it has no text."""
    ids = wrap.xpath(".//div[@data-post]/@data-post")
    if not ids or not ids[0].rsplit("/", 1)[-1].isdigit():
        return None, False
    texts = wrap.xpath(
        f".//*[{_has_class('tgme_widget_message_text')} and not(ancestor::a[{_has_class('tgme_widget_message_reply')}])]"
    )
    if not texts or not _collapse(texts[0].text_content()):
        return None, True
    markup = etree.tostring(wrap, encoding="unicode", method="html")  # before the <br> rewrite below
    text_element = texts[0]
    for br in text_element.iter("br"):
        br.tail = " " + (br.tail or "")
    permalink = f"https://t.me/{ids[0]}"  # from `data-post`, never from a link in the page: it is the document's identity
    views = wrap.xpath(f".//*[{_has_class('tgme_widget_message_views')}]")
    return (
        Post(
            message_id=int(ids[0].rsplit("/", 1)[-1]),
            permalink=permalink,
            text=_collapse(text_element.text_content()),
            published_at=(wrap.xpath("string(.//time/@datetime)") or None),
            views=_count(views[0].text_content()) if views else None,
            links=_links(text_element, base),
            html=markup,
        ),
        True,
    )


def parse(body: bytes, final_url: str) -> Channel:
    """Parse one channel page. Raises `ParseFailure` (`parse_error`) when it has neither a header nor a post."""
    try:
        root = html.document_fromstring(body, parser=html.HTMLParser(encoding="utf-8"))
    except (etree.ParserError, etree.XMLSyntaxError, ValueError) as exc:
        raise ParseFailure(Reason.PARSE_ERROR, f"markup not processable: {type(exc).__name__}") from exc

    title = _first_text(root, "tgme_channel_info_header_title")
    handle = _first_text(root, "tgme_channel_info_header_username")
    posts: list[Post] = []
    skipped = 0
    wraps = root.xpath(f"//div[{_has_class('tgme_widget_message_wrap')}]")
    for wrap in wraps:
        post, is_post = _post(wrap, final_url)
        if post is not None:
            posts.append(post)
        elif is_post:
            skipped += 1
    if title is None and handle is None and not posts and not skipped:
        raise ParseFailure(Reason.PARSE_ERROR, "page has neither a channel header nor posts")

    older = root.xpath(f"//a[{_has_class('tme_messages_more')} and @href and not(@data-after)]/@href")
    return Channel(
        network=NETWORK,
        title=title,
        handle=handle,
        profile_url=f"https://t.me/{handle.removeprefix('@')}" if handle else None,
        followers=_followers(root),
        posts=tuple(posts),
        skipped=skipped,
        older_url=urljoin(final_url, older[0]) if older else None,
    )
