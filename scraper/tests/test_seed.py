from iw_scraper.seed import KNF_URL, seed_knf


async def test_the_knf_source_is_inserted_once(pool):
    first = await seed_knf(pool)
    second = await seed_knf(pool)

    rows = await pool.fetch("SELECT id::text, platform, source_kind, target_modules, active FROM sources WHERE url = $1", KNF_URL)
    assert first is not None and second is None
    assert [(r["id"], r["platform"], r["source_kind"], list(r["target_modules"]), r["active"]) for r in rows] == [
        (first, "web", "third_party", ["M3"], True)
    ]
