"""gold-set-evaluation: "Stored calibration run" and the store half of "Module that never ran".

Postgres only (TEST_DATABASE_URL, skipped without it): the transaction and the latest-run query are the point.
"""

from __future__ import annotations

import copy
import uuid

import pytest

from investwatch_analytics.evaluation.metrics import curve
from investwatch_analytics.evaluation.store import write_run
from investwatch_analytics.storage import StoreError, StoreMisconfigured, StoreUnavailable
from test_storage import pg_url  # noqa: F401  (session fixture: throwaway database from tests/sql/schema.sql)

# The API's query (api/src/investwatch_api/db/sql.py latest_calibration_run), restated as SQL.
LATEST_SQL = """
SELECT threshold, tp, fp, fn, tn, precision, recall, f1, labeled_samples FROM calibration_points
WHERE module = %(m)s AND run_id = (
    SELECT run_id FROM calibration_points WHERE module = %(m)s ORDER BY computed_at DESC, run_id DESC LIMIT 1)
ORDER BY threshold
"""


def report(run_id: str, computed_at: str = "2026-11-21T23:00:00Z", *, m2_scores=(0.9, 0.2), not_run=("M1",)):
    pairs = [(m2_scores[0], True), (m2_scores[1], False)]
    modules = {"M2": {"status": "evaluated", "labeled_samples": 2, "points": curve(pairs)},
               "M3": {"status": "evaluated", "labeled_samples": 1, "points": curve([(0.8, True)])}}
    for m in not_run:
        modules[m] = {"status": "not_run", "labeled_samples": 3, "points": []}
    return {"run": {"run_id": run_id, "computed_at": computed_at}, "modules": modules}


@pytest.fixture
def db(pg_url):  # noqa: F811
    import psycopg

    with psycopg.connect(pg_url, autocommit=True) as conn:
        conn.execute("DELETE FROM calibration_points")
    yield pg_url


def rows(url, sql="SELECT count(*) FROM calibration_points", **params):
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(url, row_factory=dict_row) as conn:
        return conn.execute(sql, params or None).fetchall()


def latest(url, module):
    return rows(url, LATEST_SQL, m=module)


def count(url):
    return rows(url)[0]["count"]


def rid() -> str:
    return str(uuid.uuid4())


def test_one_run_writes_19_rows_per_evaluated_module(db):
    r = report(rid())
    assert write_run(db, r) == {"M2": "inserted", "M3": "inserted"}
    assert count(db) == 38
    runs = rows(db, "SELECT DISTINCT run_id, computed_at FROM calibration_points")
    assert len(runs) == 1 and str(runs[0]["run_id"]) == r["run"]["run_id"]


def test_rows_are_what_the_api_returns(db):
    r = report(rid())
    write_run(db, r)
    got = latest(db, "M2")
    want = [{**p, "labeled_samples": 2} for p in r["modules"]["M2"]["points"]]
    assert got == want


def test_same_run_again_writes_nothing(db):
    r = report(rid())
    write_run(db, r)
    assert write_run(db, report(r["run"]["run_id"], "2026-11-22T01:00:00Z")) == {"M2": "unchanged", "M3": "unchanged"}
    assert count(db) == 38
    assert {str(x["computed_at"]) for x in rows(db, "SELECT DISTINCT computed_at FROM calibration_points")} == {
        "2026-11-21 23:00:00+00:00"}


def test_rolled_back_code_refreshes_the_older_run(db):
    a, b = rid(), rid()
    write_run(db, report(a, "2026-11-21T23:00:00Z"))
    write_run(db, report(b, "2026-11-21T23:30:00Z", m2_scores=(0.4, 0.6)))
    assert latest(db, "M2")[9]["tp"] == 0  # b: positive at 0.4 is below 0.5
    assert write_run(db, report(a, "2026-11-22T00:00:00Z")) == {"M2": "refreshed", "M3": "refreshed"}
    assert count(db) == 76
    assert latest(db, "M2")[9]["tp"] == 1  # a again


def test_failure_on_the_last_row_leaves_no_row(db):
    r = report(rid())
    r["modules"]["M3"]["points"][-1]["tp"] = -1  # violates ck_calibration_points_counts
    with pytest.raises(StoreError) as exc:
        write_run(db, r)
    assert "sqlstate 23514" in str(exc.value)
    assert count(db) == 0


def test_not_run_module_keeps_its_older_run(db):
    old = report(rid(), "2026-11-21T22:00:00Z", not_run=())
    old["modules"]["M1"] = {"status": "evaluated", "labeled_samples": 4, "points": curve([(0.7, True)])}
    write_run(db, old)
    assert write_run(db, report(rid(), "2026-11-21T23:00:00Z")) == {"M2": "inserted", "M3": "inserted"}
    m1 = latest(db, "M1")
    assert len(m1) == 19 and m1[0]["labeled_samples"] == 4


def test_f1_is_written(db):
    write_run(db, report(rid()))
    assert all(r["f1"] is not None for r in latest(db, "M2"))


def test_unreachable_server(db):
    from psycopg.conninfo import make_conninfo

    dead = make_conninfo(db, port=1, password="s3cret-pw")
    with pytest.raises(StoreUnavailable) as exc:
        write_run(dead, report(rid()), connect_timeout=2)
    assert "s3cret-pw" not in str(exc.value) and dead not in str(exc.value)
    assert count(db) == 0


@pytest.mark.parametrize("dsn", ["postgresql://u:s3cret-pw@[bad", "host=x password='s3cret-pw"])
def test_bad_url(dsn):
    with pytest.raises(StoreMisconfigured) as exc:
        write_run(dsn, report(rid()))
    assert "s3cret-pw" not in str(exc.value)


def test_report_is_not_modified(db):
    r = report(rid())
    before = copy.deepcopy(r)
    write_run(db, r)
    assert r == before
