"""What the scraper collected and what failed, read from `sources`, `documents` and `job_errors`.

    python -m iw_scraper.report [--since HOURS] [--json]   (needs DATABASE_URL)

Read only. The schema keeps the last run of each source and nothing older, so the report shows counts and
the last status and never a rate over past runs. Sources appear by id and name, never by URL, and
`job_errors.detail` is never read.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import asyncpg

from iw_scraper.events import utc_iso
from iw_scraper.logs import configure_logging

log = logging.getLogger(__name__)

DEFAULT_HOURS = 24
MAX_HOURS = 24 * 365 * 10  # ten years; far larger values overflow `datetime` arithmetic

NOTE = "Run statuses are of the last run only, one per source; the database keeps no run history."


@dataclass(frozen=True)
class Rows:
    """What the three queries return: plain mappings, so `build_report` needs no database.

    `sources`: id, name, platform, source_kind, active, last_run_status, last_run_at, documents_total,
    documents_window, latest_fetched_at. `errors`: source_id (or None), reason, count, inside the window.
    `documents`: platform, source_kind, total, with_html, over all documents.
    """

    sources: Sequence[Mapping]
    errors: Sequence[Mapping]
    documents: Sequence[Mapping]


@dataclass(frozen=True)
class SourceEntry:
    id: str
    name: str
    platform: str
    source_kind: str
    last_run_status: str | None
    last_run_at: datetime | None
    documents_total: int
    documents_window: int
    latest_fetched_at: datetime | None
    errors: dict[str, int]


@dataclass(frozen=True)
class Report:
    hours: int
    since: datetime
    until: datetime
    active: tuple[SourceEntry, ...]
    inactive: tuple[SourceEntry, ...]
    never_run: tuple[SourceEntry, ...]
    no_documents: tuple[SourceEntry, ...]
    unattributed_errors: dict[str, int]
    errors: dict[str, int]
    documents_total: int
    by_platform: dict[str, int]
    by_kind: dict[str, int]
    html_documents: int
    html_share: float | None


def window_start(now: datetime, hours: int) -> datetime:
    return now - timedelta(hours=hours)


def _sorted(counts: Mapping[str, int]) -> dict[str, int]:
    return dict(sorted(counts.items()))


def _entry(row: Mapping, errors: Mapping[str, int]) -> SourceEntry:
    return SourceEntry(
        id=row["id"], name=row["name"], platform=row["platform"], source_kind=row["source_kind"],
        last_run_status=row["last_run_status"], last_run_at=row["last_run_at"],
        documents_total=row["documents_total"], documents_window=row["documents_window"],
        latest_fetched_at=row["latest_fetched_at"], errors=_sorted(errors),
    )


def build_report(rows: Rows, *, hours: int, now: datetime) -> Report:
    errors_by_source: dict[str, Counter] = {}
    total_errors: Counter = Counter()
    for row in rows.errors:
        total_errors[row["reason"]] += row["count"]
        errors_by_source.setdefault(row["source_id"], Counter())[row["reason"]] += row["count"]

    entries = [(row["active"], _entry(row, errors_by_source.get(row["id"], {}))) for row in rows.sources]
    active = tuple(entry for is_active, entry in entries if is_active)
    known = {row["id"] for row in rows.sources}
    unattributed: Counter = Counter()
    for source_id, counts in errors_by_source.items():
        if source_id not in known:
            unattributed.update(counts)

    by_platform: Counter = Counter()
    by_kind: Counter = Counter()
    for row in rows.documents:
        by_platform[row["platform"]] += row["total"]
        by_kind[row["source_kind"]] += row["total"]
    documents_total = sum(by_platform.values())
    html_documents = sum(row["with_html"] for row in rows.documents)

    return Report(
        hours=hours, since=window_start(now, hours), until=now,
        active=active,
        inactive=tuple(entry for is_active, entry in entries if not is_active),
        never_run=tuple(entry for entry in active if entry.last_run_at is None),
        no_documents=tuple(entry for entry in active if entry.documents_total == 0),
        unattributed_errors=_sorted(unattributed),
        errors=_sorted(total_errors),
        documents_total=documents_total,
        by_platform=_sorted(by_platform),
        by_kind=_sorted(by_kind),
        html_documents=html_documents,
        html_share=html_documents / documents_total if documents_total else None,
    )


def _moment(value: datetime | None) -> str | None:
    return utc_iso(value) if value else None


def _entry_dict(entry: SourceEntry) -> dict:
    return {
        "id": entry.id, "name": entry.name, "platform": entry.platform, "source_kind": entry.source_kind,
        "last_run_status": entry.last_run_status, "last_run_at": _moment(entry.last_run_at),
        "documents_total": entry.documents_total, "documents_window": entry.documents_window,
        "latest_fetched_at": _moment(entry.latest_fetched_at), "errors": entry.errors,
    }


def _ref(entry: SourceEntry) -> dict:
    return {"id": entry.id, "name": entry.name}


def render_json(report: Report) -> str:
    """One JSON object on one line."""
    body = {
        "note": NOTE,
        "window": {"hours": report.hours, "since": utc_iso(report.since), "until": utc_iso(report.until)},
        "sources": [_entry_dict(entry) for entry in report.active],
        "never_run": [_ref(entry) for entry in report.never_run],
        "no_documents": [_ref(entry) for entry in report.no_documents],
        "unattributed_errors": report.unattributed_errors,
        "inactive_sources": [_entry_dict(entry) for entry in report.inactive],
        "totals": {
            "documents": report.documents_total,
            "by_platform": report.by_platform,
            "by_source_kind": report.by_kind,
            "html_documents": report.html_documents,
            "html_share": report.html_share,
            "errors": report.errors,
        },
    }
    return json.dumps(body) + "\n"


def _counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}: {value}" for key, value in counts.items()) or "none"


def _source_lines(entry: SourceEntry) -> list[str]:
    return [
        f"{entry.name} ({entry.id}): {entry.platform}, {entry.source_kind}",
        f"  last run: {entry.last_run_status or 'never'} at {_moment(entry.last_run_at) or 'n/a'}",
        f"  documents: {entry.documents_total} total, {entry.documents_window} in the window, "
        f"latest {_moment(entry.latest_fetched_at) or 'n/a'}",
        f"  errors in the window: {_counts(entry.errors)}",
    ]


def _names(entries: Sequence[SourceEntry]) -> str:
    return ", ".join(f"{entry.name} ({entry.id})" for entry in entries) or "none"


def render_table(report: Report) -> str:
    share = "n/a" if report.html_share is None else f"{report.html_share:.0%}"
    lines = [
        f"Scraper report, last {report.hours} h ({utc_iso(report.since)} to {utc_iso(report.until)})",
        NOTE,
        "",
        f"Active sources ({len(report.active)})",
    ]
    for entry in report.active:
        lines += _source_lines(entry)
    lines += [
        "",
        f"Never run: {_names(report.never_run)}",
        f"No documents: {_names(report.no_documents)}",
        f"Unattributed errors in the window: {_counts(report.unattributed_errors)}",
        "",
        f"Inactive sources ({len(report.inactive)})",
    ]
    for entry in report.inactive:
        lines += _source_lines(entry)
    lines += [
        "",
        "Totals",
        f"  documents: {report.documents_total}",
        f"  by platform: {_counts(report.by_platform)}",
        f"  by source kind: {_counts(report.by_kind)}",
        f"  with raw HTML stored: {report.html_documents} ({share})",
        f"  errors in the window: {_counts(report.errors)}",
    ]
    return "\n".join(lines) + "\n"


# Ids are cast to text so they compare and serialise as strings; dates stay `timestamptz`. Only counts and
# `reason` come from `job_errors`: `detail` and every URL column are never selected.
_SOURCES = """
SELECT s.id::text AS id, s.name, s.platform, s.source_kind, s.active, s.last_run_status, s.last_run_at,
       count(d.id) AS documents_total,
       count(d.id) FILTER (WHERE d.fetched_at >= $1) AS documents_window,
       max(d.fetched_at) AS latest_fetched_at
FROM sources s LEFT JOIN documents d ON d.source_id = s.id
GROUP BY s.id ORDER BY s.name, s.id
"""
_ERRORS = """
SELECT source_id::text AS source_id, reason, count(*) AS count
FROM job_errors WHERE occurred_at >= $1 GROUP BY source_id, reason
"""
_DOCUMENTS = """
SELECT platform, source_kind, count(*) AS total, count(html_object_key) AS with_html
FROM documents GROUP BY platform, source_kind
"""


async def collect(conn, *, hours: int, now: datetime) -> Report:
    """The report of the three tables, read in one read-only repeatable-read transaction (one snapshot, enforced by the database)."""
    start = window_start(now, hours)
    async with conn.transaction(isolation="repeatable_read", readonly=True):
        rows = Rows(
            sources=await conn.fetch(_SOURCES, start),
            errors=await conn.fetch(_ERRORS, start),
            documents=await conn.fetch(_DOCUMENTS),
        )
    return build_report(rows, hours=hours, now=now)


def _hours(value: str) -> int:
    if not (value.isascii() and value.isdigit() and 0 < int(value) <= MAX_HOURS):
        raise argparse.ArgumentTypeError(f"{value!r} is not a whole number of hours from 1 to {MAX_HOURS}")
    return int(value)


def parse_args(argv: Sequence[str]) -> tuple[int, bool]:
    """(window hours, json?). A bad value exits with status 2 and a usage message on stderr."""
    parser = argparse.ArgumentParser(prog="python -m iw_scraper.report", description=__doc__.splitlines()[0])
    parser.add_argument("--since", type=_hours, default=DEFAULT_HOURS, metavar="HOURS", help="window in hours (default 24)")
    parser.add_argument("--json", action="store_true", help="print one JSON object instead of the table")
    args = parser.parse_args(argv)
    return args.since, args.json


async def run(argv: Sequence[str], dsn: str | None, *, now: datetime | None = None) -> int:
    """The exit code. The arguments are checked before any connection; stdout gets the report and nothing else."""
    hours, as_json = parse_args(argv)
    if not dsn:
        log.error("DATABASE_URL is not set")
        return 1
    try:
        conn = await asyncpg.connect(dsn)
        try:
            built = await collect(conn, hours=hours, now=now or datetime.now(UTC))
        finally:
            await conn.close()
    except (OSError, TimeoutError, asyncpg.PostgresError, asyncpg.InterfaceError, ValueError) as error:
        # Only the type: a malformed DSN raises a ValueError whose message quotes part of the password.
        log.error("report failed: %s (check DATABASE_URL)", type(error).__name__)
        return 1
    sys.stdout.write(render_json(built) if as_json else render_table(built))
    return 0


def main() -> None:
    configure_logging(sys.stderr)  # stdout is the report
    sys.exit(asyncio.run(run(sys.argv[1:], os.environ.get("DATABASE_URL"))))


if __name__ == "__main__":
    main()
