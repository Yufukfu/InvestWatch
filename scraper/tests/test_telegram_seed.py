"""The Telegram seed rows (`scraper/seeds/telegram.toml`): what each row is, that it is a valid `sources` record and
that a channel is only a candidate for a module, never a finding. The loader of `scraper-v2-sources` reads every `*.toml`
of the directory: the last tests run the real loader and the real `sources` table."""

import json
import tomllib
import uuid
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from iw_scraper.app import allowed_urls
from iw_scraper.config import contracts_dir
from iw_scraper.pgstore import PgSourceStore
from iw_scraper.seed import SEEDS_DIR, load_seed_dir, seed_sources
from iw_scraper.social.telegram import valid_url

SEED = Path(__file__).parent.parent / "seeds" / "telegram.toml"


@pytest.fixture(scope="module")
def rows() -> dict[str, dict]:
    entries = tomllib.loads(SEED.read_text(encoding="utf-8"))["source"]
    return {entry["url"].rsplit("/", 1)[-1]: entry for entry in entries}


def test_the_four_demo_channels_are_seeded(rows):
    assert set(rows) == {"rarecryptosignals", "crypto_sygnaly", "SubeTradingPL", "kdpwiadomosci"}


def test_signal_channels_are_m3_candidates_with_unknown_registry_status(rows):
    for handle in ("crypto_sygnaly", "SubeTradingPL"):
        assert (rows[handle]["source_kind"], rows[handle]["target_modules"]) == ("unknown", ["M3"])


def test_the_promotion_channel_and_the_news_control_are_m1_third_party(rows):
    for handle in ("rarecryptosignals", "kdpwiadomosci"):
        assert (rows[handle]["source_kind"], rows[handle]["target_modules"]) == ("third_party", ["M1"])


def test_every_row_is_a_channel_preview_url_on_platform_other(rows):
    assert all(row["platform"] == "other" and valid_url(row["url"]) for row in rows.values())


def test_runs_are_staggered_inside_one_hour_so_the_domain_is_not_hit_at_once(rows):
    crons = {handle: row["schedule_cron"] for handle, row in rows.items()}

    assert crons == {
        "rarecryptosignals": "15 */6 * * *",
        "crypto_sygnaly": "25 */6 * * *",
        "SubeTradingPL": "35 */6 * * *",
        "kdpwiadomosci": "45 */6 * * *",
    }


def test_every_row_validates_against_the_source_schema(rows):
    schema = json.loads((contracts_dir() / "schemas" / "source.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    for row in rows.values():
        record = {"id": str(uuid.uuid4()), "active": True, **row}
        assert [e.message for e in validator.iter_errors(record)] == []


def telegram_entries():
    return [e for e in load_seed_dir(SEEDS_DIR) if e.url.startswith("https://t.me/s/")]


def test_the_directory_loader_reads_the_four_channels_next_to_the_web_sources():
    entries = load_seed_dir(SEEDS_DIR)

    assert {e.url.rsplit("/", 1)[-1] for e in telegram_entries()} == {
        "rarecryptosignals", "crypto_sygnaly", "SubeTradingPL", "kdpwiadomosci",
    }
    assert {e.platform for e in telegram_entries()} == {"other"}
    assert any(e.platform == "web" for e in entries)


async def test_seeding_twice_leaves_one_row_per_channel(pool):
    entries = telegram_entries()

    first = await seed_sources(pool, entries)
    second = await seed_sources(pool, entries)

    assert (first, second) == ((4, 0), (0, 4))
    rows = await pool.fetch("SELECT url, platform, source_kind, target_modules FROM sources ORDER BY url")
    assert [(r["url"], r["platform"], r["source_kind"], list(r["target_modules"])) for r in rows] == [
        ("https://t.me/s/SubeTradingPL", "other", "unknown", ["M3"]),
        ("https://t.me/s/crypto_sygnaly", "other", "unknown", ["M3"]),
        ("https://t.me/s/kdpwiadomosci", "other", "third_party", ["M1"]),
        ("https://t.me/s/rarecryptosignals", "other", "third_party", ["M1"]),
    ]


async def test_a_seeded_channel_is_allowed_by_the_url_guard(pool):
    await seed_sources(pool, telegram_entries())

    guard = await allowed_urls(PgSourceStore(pool), [], (80, 443))()

    guard.check("https://t.me/s/kdpwiadomosci")  # raises when the host is not allowed
