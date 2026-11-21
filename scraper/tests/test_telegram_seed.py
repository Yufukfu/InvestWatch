"""The Telegram seed rows (`scraper/seeds/telegram.toml`): what each row is, that it is a valid `sources` record and
that a channel is only a candidate for a module, never a finding. Loading and idempotency belong to the seed loader
of `scraper-v2-sources`, which reads every `*.toml` in the directory."""

import json
import tomllib
import uuid
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from iw_scraper.config import contracts_dir
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
