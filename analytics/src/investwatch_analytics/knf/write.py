"""Write the registry CSV and its provenance file safely (design decisions 2 and 7).

Everything is built in memory, written to temporary files next to the targets, loaded back with
`Registry.from_csv`, and only then renamed over the old files. A failed run leaves the old files untouched.
"""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..registry import Registry, RegistryError
from . import KnfError
from .build import BuildReport, Firm, normalize_name
from .fetch import FetchedList

COLUMNS = ("id", "name", "aliases", "type", "country", "website_domains", "source_url")
LOADER_VERSION = "1.0"
SOURCE = "Komisja Nadzoru Finansowego, https://www.knf.gov.pl (reuse with the source named, KNF legal note)"
MIN_KEPT_SHARE = 0.5  # a list that loses more than half of its records since the last load fails (count_dropped)


def meta_path(csv_path: Path) -> Path:
    return csv_path.with_name(csv_path.stem + ".meta.json")


def read_previous(csv_path: Path) -> dict[str, tuple[str, str]]:
    """normalized name -> (id, name) of the previous CSV, or {} when there is none."""
    if not csv_path.exists():
        return {}
    try:
        registry = Registry.from_csv(csv_path)
    except RegistryError as exc:
        raise KnfError("invalid_output", f"previous registry unreadable: {exc}") from exc
    return {normalize_name(f.name): (f.id, f.name) for f in registry.firms}


def read_meta(csv_path: Path) -> dict | None:
    path = meta_path(csv_path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise KnfError("invalid_output", f"{path}: unreadable provenance ({exc})") from exc


def check_counts(fetched: dict[str, FetchedList], previous_meta: dict | None, *, accept_drop: bool) -> None:
    """`count_dropped` for an empty list, or one that lost more than half of its records since the last load."""
    for key, fl in fetched.items():
        now = len(fl.records)
        before = ((previous_meta or {}).get("lists", {}).get(key) or {}).get("records")
        if now == 0:
            raise KnfError("count_dropped", f"{key}: 0 records (previously {before})")
        if before and now < MIN_KEPT_SHARE * before and not accept_drop:
            raise KnfError("count_dropped", f"{key}: {now} records, previously {before}; rerun with "
                                            f"--accept-drop after checking the KNF page")


def _cell(value: str) -> str:
    return " ".join(value.replace("|", " ").split())  # `|` separates list items in the CSV


def render_csv(firms: list[Firm]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(COLUMNS)
    for f in firms:
        writer.writerow([f.id, _cell(f.name), "|".join(_cell(a) for a in f.aliases), f.type, f.country or "",
                         "|".join(f.domains), f.source_url])
    return buf.getvalue()


@dataclass
class Summary:
    firms: int
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    renamed: list[tuple[str, str]] = field(default_factory=list)
    dropped_aliases: int = 0
    dropped_domains: int = 0
    unknown_countries: int = 0
    curated_domains: int = 0
    curated_unverified: int = 0


def summarize(firms: list[Firm], report: BuildReport, previous: dict[str, tuple[str, str]]) -> Summary:
    prev_ids = {pid: name for pid, name in previous.values()}
    ids = {f.id for f in firms}
    return Summary(
        firms=len(firms),
        added=sorted(f.name for f in firms if f.id not in prev_ids) if previous else [],
        removed=sorted(name for pid, name in prev_ids.items() if pid not in ids),
        renamed=report.renamed,
        dropped_aliases=len(report.dropped_aliases),
        dropped_domains=len(report.dropped_domains),
        unknown_countries=len(report.unknown_countries),
        curated_domains=len(report.curated),
        curated_unverified=sum(1 for *_, verified in report.curated if not verified),
    )


def render_meta(fetched: dict[str, FetchedList], firms: list[Firm], summary: Summary, fetched_at: datetime) -> dict:
    by_url: dict[str, int] = {}
    for f in firms:
        by_url[f.source_url] = by_url.get(f.source_url, 0) + 1
    return {
        "source": SOURCE,
        "fetched_at": fetched_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "loader_version": LOADER_VERSION,
        "firms": len(firms),
        "lists": {key: {"url": fl.source.url, "type": fl.source.type, "records": len(fl.records),
                        "firms": by_url.get(fl.source.url, 0), "pages": fl.pages, "skipped": fl.skipped}
                  for key, fl in fetched.items()},
        "domains": {"knf": sum(len(f.domains) for f in firms) - summary.curated_domains,
                    "curated": summary.curated_domains, "curated_unverified": summary.curated_unverified},
        "unknown_countries": summary.unknown_countries,
    }


def _write_temp(target: Path, text: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return Path(name)


def write_registry(csv_path: Path, csv_text: str, meta: dict) -> None:
    """Write both files atomically. The CSV is loaded back first; on any failure the old files stay."""
    temps: list[Path] = []
    try:
        tmp_csv = _write_temp(csv_path, csv_text)
        temps.append(tmp_csv)
        try:
            Registry.from_csv(tmp_csv)
        except RegistryError as exc:
            raise KnfError("invalid_output", f"generated registry does not load: {exc}") from exc
        tmp_meta = _write_temp(meta_path(csv_path), json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
        temps.append(tmp_meta)
        os.replace(tmp_csv, csv_path)
        os.replace(tmp_meta, meta_path(csv_path))
    finally:
        for t in temps:
            t.unlink(missing_ok=True)
