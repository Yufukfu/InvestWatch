import pytest

from iw_scraper.seed import KNF_URL, cron_from, seed_knf


async def test_the_knf_source_is_inserted_once(pool):
    first = await seed_knf(pool)
    second = await seed_knf(pool)

    rows = await pool.fetch("SELECT id::text, platform, source_kind, target_modules, active FROM sources WHERE url = $1", KNF_URL)
    assert first is not None and second is None
    assert [(r["id"], r["platform"], r["source_kind"], list(r["target_modules"]), r["active"]) for r in rows] == [
        (first, "web", "third_party", ["M3"], True)
    ]


async def test_the_cron_is_stored_when_given(pool):
    await seed_knf(pool, cron="0 * * * *")

    assert await pool.fetchval("SELECT schedule_cron FROM sources WHERE url = $1", KNF_URL) == "0 * * * *"


def test_the_cron_comes_from_the_first_argument():
    assert cron_from(["seed", "0 * * * *"]) == "0 * * * *"
    assert cron_from(["seed"]) is None


@pytest.mark.parametrize("bad", ["not a cron", "61 * * * *", "* * * *", ""])
def test_an_invalid_cron_stops_the_seed_before_it_connects(bad):
    with pytest.raises(SystemExit, match="invalid cron"):
        cron_from(["seed", bad])
