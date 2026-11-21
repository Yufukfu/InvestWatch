"""Write one evaluation run into `calibration_points` (gold-set-evaluation "Stored calibration run", design 7).

All modules in one transaction, so `GET /api/calibration` never serves half a run. Per evaluated module:
- `unchanged`: the module's latest run (the API's ordering) already has this `run_id`: nothing is written;
- `refreshed`: rows with this `run_id` exist but another run is newer (code rolled back): their
  `computed_at` moves to this run's time, so the API serves them again;
- `inserted`: otherwise, the 19 points are inserted.
`not_run` modules get no rows. Errors use the worker's store taxonomy and never quote the DSN.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from ..storage import StoreError, StoreMisconfigured, StoreUnavailable

COLUMNS = ("run_id", "module", "threshold", "tp", "fp", "fn", "tn", "precision", "recall", "f1",
           "labeled_samples", "computed_at")
_LATEST = ("SELECT run_id FROM calibration_points WHERE module = %s "
           "ORDER BY computed_at DESC, run_id DESC LIMIT 1")
_REFRESH = "UPDATE calibration_points SET computed_at = %s WHERE run_id = %s AND module = %s"
_INSERT = (f"INSERT INTO calibration_points ({', '.join(COLUMNS)}) VALUES ({', '.join(['%s'] * len(COLUMNS))}) "
           "ON CONFLICT (run_id, module, threshold) DO NOTHING")


def check_dsn(dsn: str) -> None:
    """Raise StoreMisconfigured for a DSN libpq cannot parse; the message never quotes it."""
    from psycopg.conninfo import conninfo_to_dict

    try:
        conninfo_to_dict(dsn)
        malformed = False
    except Exception:
        malformed = True
    if malformed:  # raised outside the except block, so the libpq error (it may quote the password) is not kept
        raise StoreMisconfigured("DATABASE_URL is malformed")


def write_run(dsn: str, report: dict, *, connect_timeout: int = 5) -> dict[str, str]:
    import psycopg

    check_dsn(dsn)

    run_id = uuid.UUID(report["run"]["run_id"])
    computed_at = datetime.fromisoformat(report["run"]["computed_at"].replace("Z", "+00:00"))
    evaluated = {m: e for m, e in sorted(report["modules"].items()) if e["status"] == "evaluated"}
    outcome: dict[str, str] = {}
    try:
        with psycopg.connect(dsn, connect_timeout=connect_timeout) as conn, conn.transaction():
            for module, entry in evaluated.items():
                row = conn.execute(_LATEST, (module,)).fetchone()
                if row is not None and row[0] == run_id:
                    outcome[module] = "unchanged"
                    continue
                if conn.execute(_REFRESH, (computed_at, run_id, module)).rowcount:
                    outcome[module] = "refreshed"
                    continue
                with conn.cursor() as cur:
                    cur.executemany(_INSERT, [_row(run_id, module, p, entry, computed_at) for p in entry["points"]])
                outcome[module] = "inserted"
    except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
        # libpq names host and port, never the password; keep the class and first line only anyway.
        first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
        raise StoreUnavailable(f"{type(exc).__name__}: {first_line}") from None
    except psycopg.Error as exc:
        # Constraint or grant problems: class and SQLSTATE only, driver messages can echo row values.
        raise StoreError(f"{type(exc).__name__} (sqlstate {exc.sqlstate})") from None
    return outcome


def _row(run_id: uuid.UUID, module: str, point: dict, entry: dict, computed_at: datetime) -> tuple[Any, ...]:
    return (run_id, module, point["threshold"], point["tp"], point["fp"], point["fn"], point["tn"],
            point["precision"], point["recall"], point["f1"], entry["labeled_samples"], computed_at)
