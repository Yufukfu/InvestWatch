import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from iw_scraper.config import contracts_dir
from iw_scraper.ingest.document import build_document
from iw_scraper.parsing import ParseFailure
from iw_scraper.social.telegram import Link, build_page, parse
from iw_scraper.types import Reason, Source

FIXTURES = Path(__file__).parent / "fixtures"
SUBE_URL = "https://t.me/s/SubeTradingPL"
FETCHED = datetime(2026, 11, 21, 12, 30, 5, tzinfo=timezone.utc)
SOURCE = Source(
    id="11111111-1111-4111-8111-111111111111", name="Sube", platform="other", url=SUBE_URL,
    source_kind="unknown", target_modules=("M3",), active=True,
)


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def channel_page(counter: str | None = "1.5K", posts: str = "", older: str | None = None) -> bytes:
    """A minimal channel page in Telegram's markup; the real pages are the fixtures, this varies one field."""
    counters = (
        f'<div class="tgme_channel_info_counters"><div class="tgme_channel_info_counter">'
        f'<span class="counter_value">{counter}</span> <span class="counter_type">subscribers</span></div></div>'
        if counter is not None
        else ""
    )
    more = f'<a href="{older}" class="tme_messages_more js-messages_more"></a>' if older else ""
    return (
        '<html><body><div class="tgme_channel_info"><div class="tgme_channel_info_header">'
        '<div class="tgme_channel_info_header_title"><span dir="auto">Kanał</span></div>'
        '<div class="tgme_channel_info_header_username"><a href="https://t.me/kanalx">@kanalx</a></div></div>'
        f"{counters}</div>{more}{posts}</body></html>"
    ).encode()


def text_post(post_id: int, text: str) -> str:
    return (
        f'<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="kanalx/{post_id}">'
        f'<div class="tgme_widget_message_text js-message_text">{text}</div>'
        f'<a class="tgme_widget_message_date" href="https://t.me/kanalx/{post_id}">'
        f'<time datetime="2026-11-20T09:15:00+00:00">09:15</time></a></div></div>'
    )


IMAGE_POST = (
    '<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="kanalx/7">'
    '<a class="tgme_widget_message_photo_wrap" href="https://t.me/kanalx/7"></a>'
    '<a class="tgme_widget_message_date" href="https://t.me/kanalx/7">'
    '<time datetime="2026-11-20T09:15:00+00:00">09:15</time></a></div></div>'
)


def test_header_of_a_real_channel():
    channel = parse(load("telegram_subetradingpl.html"), SUBE_URL)

    assert channel.title == "Sube Trading"
    assert channel.handle == "@SubeTradingPL"
    assert channel.followers == 8110


def test_text_post_fields():
    channel = parse(load("telegram_subetradingpl.html"), SUBE_URL)

    post = channel.posts[0]
    assert post.message_id == 1782
    assert post.permalink == "https://t.me/SubeTradingPL/1782"
    assert post.published_at == "2026-11-03T13:35:22+00:00"
    assert post.views == 8450
    assert post.text.startswith("także u mnie oficjalnie spoty z głowy")


def test_image_only_post_is_skipped_and_counted():
    channel = parse(load("telegram_subetradingpl.html"), SUBE_URL)

    assert len(channel.posts) == 17
    assert channel.skipped == 1
    assert 1783 not in [p.message_id for p in channel.posts]


def test_older_posts_link_is_absolute():
    channel = parse(load("telegram_subetradingpl.html"), SUBE_URL)

    assert channel.older_url == "https://t.me/s/SubeTradingPL?before=1782"


def test_line_breaks_become_single_spaces():
    channel = parse(load("telegram_kdpwiadomosci.html"), "https://t.me/s/kdpwiadomosci")

    post = next(p for p in channel.posts if p.message_id == 5187)
    assert post.text.startswith("Dostaliśmy dane inflacyjne. CPI lekko powyżej oczekiwań. CPI 0.4% MoM, Exp. 0.3%")
    assert "\n" not in post.text and "  " not in post.text


def test_post_html_holds_only_its_own_post():
    channel = parse(load("telegram_kdpwiadomosci.html"), "https://t.me/s/kdpwiadomosci")

    post = next(p for p in channel.posts if p.message_id == 5187)
    assert 'data-post="kdpwiadomosci/5187"' in post.html
    assert "kdpwiadomosci/5186" not in post.html
    assert "kdpwiadomosci/5188" not in post.html


def test_link_in_post_is_kept_as_pointer():
    channel = parse(load("telegram_rarecryptosignals_before.html"), "https://t.me/s/rarecryptosignals?before=2000")

    post = next(p for p in channel.posts if p.message_id == 1999)
    assert post.text == "Update rynku: https://youtu.be/ms4VIbaHo7Y"
    assert post.links == (Link("https://youtu.be/ms4VIbaHo7Y", "https://youtu.be/ms4VIbaHo7Y"),)


def test_subscribers_with_suffix():
    assert parse(load("telegram_rarecryptosignals_before.html"), SUBE_URL).followers == 36100
    assert parse(channel_page(counter="1.2M"), SUBE_URL).followers == 1200000


def test_small_plain_count():
    assert parse(channel_page(counter="387"), SUBE_URL).followers == 387


def test_no_counter_gives_null_followers():
    channel = parse(channel_page(counter=None, posts=text_post(5, "Cześć")), SUBE_URL)

    assert channel.followers is None
    assert [p.message_id for p in channel.posts] == [5]


def test_unreadable_counter_gives_null_followers():
    assert parse(channel_page(counter="many"), SUBE_URL).followers is None


def test_short_channel_has_no_older_link():
    channel = parse(channel_page(posts=text_post(5, "Cześć")), SUBE_URL)

    assert channel.older_url is None


def test_page_of_image_only_posts_has_no_documents():
    channel = parse(channel_page(posts=IMAGE_POST + IMAGE_POST.replace("kanalx/7", "kanalx/8")), SUBE_URL)

    assert channel.posts == ()
    assert channel.skipped == 2


def test_header_only_page_is_an_empty_channel():
    channel = parse(channel_page(), SUBE_URL)

    assert channel.posts == ()
    assert channel.skipped == 0


def test_page_that_is_not_a_channel_is_a_parse_error():
    with pytest.raises(ParseFailure) as failure:
        parse(b"<html><body><p>Preview not available</p></body></html>", SUBE_URL)

    assert failure.value.reason is Reason.PARSE_ERROR


def stored_document(post_index: int = 0, fixture: str = "telegram_subetradingpl.html") -> tuple[dict, dict]:
    """(the page dict the collector hands to ingest, the full document ingest builds from it)."""
    channel = parse(load(fixture), SUBE_URL)
    page = build_page(channel, channel.posts[post_index], http_status=200)
    document = build_document(page, SOURCE, fetched_at=FETCHED, duration_ms=120, proxy=None)
    return page, document


def schema_errors(document: dict) -> list[str]:
    schema = json.loads((contracts_dir() / "schemas" / "scraped-document.schema.json").read_text(encoding="utf-8"))
    return [e.message for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)]


def test_post_document_is_schema_valid():
    _, document = stored_document()

    assert schema_errors(document) == []


def test_post_document_fields():
    _, document = stored_document()

    assert document["url"] == "https://t.me/SubeTradingPL/1782"
    assert document["canonical_url"] == document["url"]
    assert document["title"] is None and document["lang"] is None
    assert document["platform"] == "other" and document["source_kind"] == "unknown"
    assert document["published_at"] == "2026-11-03T13:35:22+00:00"
    assert document["author"] == {
        "name": "Sube Trading", "handle": "@SubeTradingPL", "profile_url": "https://t.me/SubeTradingPL",
        "followers": 8110,
    }


def test_scrape_meta_carries_message_id_views_and_network():
    _, document = stored_document()

    assert document["scrape_meta"]["message_id"] == 1782
    assert document["scrape_meta"]["views"] == 8450
    assert document["scrape_meta"]["network"] == "telegram"
    assert document["scrape_meta"]["duration_ms"] == 120  # the fetch facts are still added by ingest


def test_post_without_views_has_null_views():
    channel = parse(channel_page(posts=text_post(5, "Cześć")), SUBE_URL)

    page = build_page(channel, channel.posts[0], http_status=200)

    assert page["scrape_meta"]["views"] is None


def test_links_keep_their_text():
    channel = parse(
        channel_page(posts=text_post(5, 'Zobacz <a href="https://x.com/a/status/1">wpis</a>')), SUBE_URL
    )

    page = build_page(channel, channel.posts[0], http_status=200)

    assert page["links"] == [{"href": "https://x.com/a/status/1", "text": "wpis"}]


def test_stored_html_is_the_post_only():
    page, _ = stored_document(fixture="telegram_kdpwiadomosci.html")

    assert 'data-post="kdpwiadomosci/5179"' in page["html"]
    assert "kdpwiadomosci/5180" not in page["html"]


def test_channel_without_a_header_gives_null_author_fields():
    channel = parse(channel_page(posts=text_post(5, "Cześć")).replace(b"tgme_channel_info_header", b"x"), SUBE_URL)

    page = build_page(channel, channel.posts[0], http_status=200)

    assert page["author"] == {"name": None, "handle": None, "profile_url": None, "followers": 1500}


def test_post_with_only_whitespace_and_line_breaks_has_no_text():
    channel = parse(channel_page(posts=text_post(5, "  <br/> \n <br/>")), SUBE_URL)

    assert channel.posts == ()
    assert channel.skipped == 1


def test_quoted_reply_text_is_not_the_post_text():
    channel = parse(load("telegram_rarecryptosignals.html"), "https://t.me/s/rarecryptosignals")
    older = parse(load("telegram_rarecryptosignals_before.html"), "https://t.me/s/rarecryptosignals?before=2000")

    post = next(p for p in older.posts if p.message_id == 1988)
    assert post.text == "$PENGU już +80%"
    assert channel.posts  # the newest page parses too


def test_reply_with_no_text_of_its_own_is_skipped():
    reply = (
        '<a class="tgme_widget_message_reply"><div class="tgme_widget_message_text js-message_reply_text">'
        "cytat</div></a>"
    )
    post = IMAGE_POST.replace('<a class="tgme_widget_message_photo_wrap"', reply + '<a class="tgme_widget_message_photo_wrap"')

    channel = parse(channel_page(posts=post), SUBE_URL)

    assert channel.posts == ()
    assert channel.skipped == 1


def test_followers_come_from_the_subscribers_counter_not_another_one():
    page = channel_page(counter=None).replace(
        b"</div></body>",
        b'<div class="tgme_channel_info_counters">'
        b'<div class="tgme_channel_info_counter"><span class="counter_value">12</span>'
        b' <span class="counter_type">photos</span></div>'
        b'<div class="tgme_channel_info_counter"><span class="counter_value">5K</span>'
        b' <span class="counter_type">subscribers</span></div></div></div></body>',
    )

    assert parse(page, SUBE_URL).followers == 5000


def test_a_counter_that_is_not_subscribers_gives_null_followers():
    page = channel_page(counter=None).replace(
        b"</div></body>",
        b'<div class="tgme_channel_info_counters"><div class="tgme_channel_info_counter">'
        b'<span class="counter_value">12</span> <span class="counter_type">photos</span></div></div></div></body>',
    )

    assert parse(page, SUBE_URL).followers is None


def test_message_without_a_numeric_id_is_ignored():
    page = channel_page(posts=text_post(5, "Cześć")).replace(b"kanalx/5", b"kanalx/abc")

    channel = parse(page, SUBE_URL)

    assert channel.posts == ()
    assert channel.skipped == 0
