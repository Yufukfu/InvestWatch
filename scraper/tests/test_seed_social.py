"""The X and YouTube seed rows (`scraper/seeds/x-youtube.toml`): what each row is, that it is a valid `sources` record,
that it seeds once, that no schedule touches it and that a scan request starts a run. The last tests use the real loader
and the real `sources` table."""

import json
import tomllib
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from arq.jobs import Job
from jsonschema import Draft202012Validator, FormatChecker

from conftest import Recorder
from iw_scraper.config import contracts_dir
from iw_scraper.jobs import QUEUE_NAME
from iw_scraper.pgstore import PgSourceStore
from iw_scraper.scan_requests import ScanRequestConsumer
from iw_scraper.scheduler import Scheduler
from iw_scraper.seed import SEEDS_DIR, load_seed_dir, seed_sources
from iw_scraper.social import x, youtube

SEED = Path(__file__).parent.parent / "seeds" / "x-youtube.toml"
X_URL = "https://x.com/uknf"
YOUTUBE_URL = "https://www.youtube.com/@UKNFpolska"
STREAM = "iw:scan-requests"
SLOT = datetime(2026, 11, 22, 6, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def rows() -> dict[str, dict]:
    return {entry["platform"]: entry for entry in tomllib.loads(SEED.read_text(encoding="utf-8"))["source"]}


def social_entries():
    return [e for e in load_seed_dir(SEEDS_DIR) if e.platform in ("x", "youtube")]


def test_the_regulators_own_x_account_and_youtube_channel_are_seeded(rows):
    assert {platform: row["url"] for platform, row in rows.items()} == {"x": X_URL, "youtube": YOUTUBE_URL}


def test_each_url_has_the_form_its_collector_accepts(rows):
    assert x.valid_url(rows["x"]["url"]) and youtube.valid_url(rows["youtube"]["url"])


def test_both_rows_are_unknown_kind_m1_sources(rows):
    assert {(r["source_kind"], tuple(r["target_modules"])) for r in rows.values()} == {("unknown", ("M1",))}


def test_no_row_has_a_schedule(rows):
    assert all("schedule_cron" not in row for row in rows.values())


def test_every_row_validates_against_the_source_schema(rows):
    schema = json.loads((contracts_dir() / "schemas" / "source.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    for row in rows.values():
        record = {"id": str(uuid.uuid4()), "active": True, **row}
        assert [e.message for e in validator.iter_errors(record)] == []


def test_the_directory_loader_reads_both_rows_next_to_the_other_sources():
    entries = load_seed_dir(SEEDS_DIR)

    assert {(e.platform, e.url, e.schedule_cron) for e in social_entries()} == {
        ("x", X_URL, None), ("youtube", YOUTUBE_URL, None),
    }
    assert any(e.platform == "web" for e in entries) and any(e.platform == "other" for e in entries)


async def test_seeding_twice_leaves_one_row_per_account(pool):
    entries = social_entries()

    first = await seed_sources(pool, entries)
    second = await seed_sources(pool, entries)

    assert (first, second) == ((2, 0), (0, 2))
    rows = await pool.fetch("SELECT url, platform, source_kind, target_modules, schedule_cron, active FROM sources ORDER BY url")
    assert [(r["url"], r["platform"], r["source_kind"], list(r["target_modules"]), r["schedule_cron"], r["active"]) for r in rows] == [
        (YOUTUBE_URL, "youtube", "unknown", ["M1"], None, True),
        (X_URL, "x", "unknown", ["M1"], None, True),
    ]


async def test_the_scheduler_never_enqueues_a_seeded_account(pool, redis):
    await seed_sources(pool, social_entries())
    scheduler = Scheduler(redis, PgSourceStore(pool), Recorder().record_error)

    enqueued = [await scheduler.tick(SLOT.replace(minute=minute)) for minute in range(0, 60, 5)]

    assert sum(enqueued) == 0 and await redis.zcard(QUEUE_NAME) == 0


@pytest.mark.parametrize(("url", "domain"), [(X_URL, "x.com"), (YOUTUBE_URL, "www.youtube.com")])
async def test_a_scan_request_for_a_seeded_account_enqueues_one_requested_run(pool, redis, url, domain):
    await seed_sources(pool, social_entries())
    source_id = str(await pool.fetchval("SELECT id FROM sources WHERE url = $1", url))
    recorder = Recorder()
    consumer = ScanRequestConsumer(redis, PgSourceStore(pool), recorder.record_error, consumer="w1", claim_idle=0.2)
    await consumer.setup()
    await redis.xadd(STREAM, {"source_id": source_id, "requested_at": datetime.now(UTC).isoformat()})

    await consumer.poll(block=0.2)

    jobs = [await Job(j.decode(), redis, _queue_name=QUEUE_NAME, _deserializer=json.loads).info() for j in await redis.zrange(QUEUE_NAME, 0, -1)]
    assert [(j.function, tuple(j.args)) for j in jobs] == [("execute_job", (source_id, domain, True))]
    assert recorder.errors == []
