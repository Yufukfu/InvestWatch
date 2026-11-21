"""The seed files: what `load_seed` and `load_seed_dir` accept and refuse. No database here."""

from pathlib import Path

import pytest

from iw_scraper.seed import SEEDS_DIR, SeedEntry, SeedError, load_seed, load_seed_dir

XTB = """
[[source]]
name = "XTB IKE"
url = "https://www.xtb.com/pl/ike"
source_kind = "firm_own"
target_modules = ["M2"]
schedule_cron = "0 6 * * *"
"""


def write(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body)
    return path


def entry(**changes: str | None) -> str:
    """The `XTB` entry with some lines replaced; a value of `None` removes that line."""
    lines: dict[str, str | None] = {
        "name": '"XTB IKE"',
        "url": '"https://www.xtb.com/pl/ike"',
        "source_kind": '"firm_own"',
        "target_modules": '["M2"]',
        "schedule_cron": '"0 6 * * *"',
    }
    lines.update(changes)
    body = "".join(f"{key} = {value}\n" for key, value in lines.items() if value is not None)
    return f"[[source]]\n{body}"


def test_a_valid_file_gives_one_entry_per_source(tmp_path):
    path = write(tmp_path, "sources.toml", XTB)

    assert load_seed(path) == [
        SeedEntry(
            name="XTB IKE",
            platform="web",
            url="https://www.xtb.com/pl/ike",
            source_kind="firm_own",
            target_modules=("M2",),
            schedule_cron="0 6 * * *",
        )
    ]


def test_platform_defaults_to_web_and_cron_to_none(tmp_path):
    path = write(tmp_path, "sources.toml", entry(schedule_cron=None))

    [loaded] = load_seed(path)

    assert (loaded.platform, loaded.schedule_cron) == ("web", None)


def test_a_source_of_unknown_registry_status_is_accepted(tmp_path):
    body = entry(name='"EY family office (negative control)"', source_kind='"unknown"', target_modules='["M3"]')
    path = write(tmp_path, "sources.toml", body)

    [loaded] = load_seed(path)

    assert (loaded.source_kind, loaded.target_modules) == ("unknown", ("M3",))


@pytest.mark.parametrize(
    "changes",
    [
        {"target_modules": "[]"},
        {"target_modules": '["M4"]'},
        {"target_modules": '["M2", "M2"]'},
        {"target_modules": '"M2"'},
        {"target_modules": "5"},
        {"name": '""'},
        {"name": '"  "'},
        {"url": '"http://www.xtb.com/pl/ike"'},
        {"url": '"https:///pl/ike"'},
        {"url": '"www.xtb.com/pl/ike"'},
        {"url": None},
        {"schedule_cron": '"every day"'},
        {"schedule_cron": '"0 0 6 * * *"'},
        {"schedule_cron": '"0 6 * *"'},
        {"schedule_cron": '"61 6 * * *"'},
        {"platform": '"myspace"'},
        {"source_kind": '"bogus"'},
        {"source_kind": None},
        {"active": "true"},
    ],
    ids=lambda changes: ",".join(f"{k}={v}" for k, v in changes.items()),
)
def test_an_invalid_entry_is_refused_with_its_file_and_position(tmp_path, changes):
    path = write(tmp_path, "sources.toml", entry(**changes))

    with pytest.raises(SeedError) as refused:
        load_seed(path)

    assert "sources.toml" in str(refused.value)
    assert "entry 1" in str(refused.value)


def test_a_refusal_names_the_entry_when_it_has_a_name(tmp_path):
    path = write(tmp_path, "sources.toml", entry(target_modules="[]"))

    with pytest.raises(SeedError, match="XTB IKE"):
        load_seed(path)


def test_one_invalid_entry_refuses_the_whole_file(tmp_path):
    good = entry(name='"A"', url='"https://a.example/x"')
    bad = entry(name='"B"', url='"https://b.example/x"', target_modules="[]")
    last = entry(name='"C"', url='"https://c.example/x"')
    path = write(tmp_path, "sources.toml", good + bad + last)

    with pytest.raises(SeedError, match="entry 2"):
        load_seed(path)


def test_a_file_that_is_not_toml_is_refused_with_its_name(tmp_path):
    path = write(tmp_path, "broken.toml", "[[source]\nname = ")

    with pytest.raises(SeedError, match="broken.toml"):
        load_seed(path)


@pytest.mark.parametrize(
    "body",
    ["# nothing here\n", "source = []\n", "source = 5\n", "extra = 1\n" + XTB],
    ids=["no tables", "empty list", "not a list of tables", "key beside the tables"],
)
def test_a_file_that_is_not_a_list_of_sources_is_refused(tmp_path, body):
    path = write(tmp_path, "empty.toml", body)

    with pytest.raises(SeedError, match="empty.toml"):
        load_seed(path)


def test_two_files_give_both_entry_lists_in_file_name_order(tmp_path):
    channel = entry(
        name='"A channel"',
        url='"https://t.me/s/example"',
        platform='"other"',
        target_modules='["M3"]',
        source_kind='"unknown"',
    )
    write(tmp_path, "telegram.toml", channel)
    write(tmp_path, "sources.toml", XTB)

    loaded = load_seed_dir(tmp_path)

    assert [(e.name, e.platform) for e in loaded] == [("XTB IKE", "web"), ("A channel", "other")]


def test_only_toml_files_of_the_directory_are_read(tmp_path):
    write(tmp_path, "sources.toml", XTB)
    write(tmp_path, "README.md", "not a seed file")
    write(tmp_path, "notes.toml.bak", "[[source]\nbroken")

    assert [e.name for e in load_seed_dir(tmp_path)] == ["XTB IKE"]


def test_the_same_url_in_two_files_refuses_the_run_and_names_both(tmp_path):
    write(tmp_path, "sources.toml", XTB)
    write(tmp_path, "telegram.toml", entry(name='"Same page again"'))

    with pytest.raises(SeedError) as refused:
        load_seed_dir(tmp_path)

    assert "XTB IKE" in str(refused.value) and "Same page again" in str(refused.value)


def test_the_same_url_twice_in_one_file_is_refused_and_names_both(tmp_path):
    path = write(tmp_path, "sources.toml", XTB + entry(name='"Twin"'))

    with pytest.raises(SeedError) as refused:
        load_seed(path)

    assert "XTB IKE" in str(refused.value) and "Twin" in str(refused.value)


def test_one_invalid_file_refuses_the_whole_directory(tmp_path):
    write(tmp_path, "sources.toml", XTB)
    write(tmp_path, "telegram.toml", entry(name='"Bad"', url='"https://t.me/s/x"', target_modules="[]"))

    with pytest.raises(SeedError, match="telegram.toml"):
        load_seed_dir(tmp_path)


def test_the_tracked_seed_files_cover_every_module():
    covered = {module for e in load_seed_dir(SEEDS_DIR) for module in e.target_modules}

    assert covered == {"M1", "M2", "M3"}


def test_every_firm_own_page_targets_m2():
    firm_own = [e for e in load_seed_dir(SEEDS_DIR) if e.source_kind == "firm_own"]

    assert firm_own and all("M2" in e.target_modules for e in firm_own)


def test_every_row_of_sources_toml_is_a_web_source():
    assert {e.platform for e in load_seed(SEEDS_DIR / "sources.toml")} == {"web"}


def test_m3_rows_of_sources_toml_are_unknown_kind_controls_or_lists():
    m3 = [e for e in load_seed(SEEDS_DIR / "sources.toml") if "M3" in e.target_modules]

    assert m3
    assert all(e.source_kind == "unknown" and ("negative control" in e.name or "list" in e.name) for e in m3)
