"""CSV report of a findings list for GET /findings/export (contract 1.3.0, issue #115)."""

from __future__ import annotations

import csv
import io

MAX_EXPORT_ROWS = 10_000
COLUMNS = ("id", "detected_at", "module", "risk_level", "score", "status", "platform", "title", "firm_name",
           "firm_registry_id", "advertiser_name", "advertiser_handle", "url", "failed_rules", "note")
# A spreadsheet reads a cell starting with one of these as a formula (CSV injection); a leading ' keeps it text.
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _cell(value) -> str:
    if value is None:
        return ""
    text = str(value)
    return "'" + text if text.startswith(_FORMULA_START) else text


def _row(f: dict) -> list[str]:
    firm, adv = f.get("firm") or {}, f.get("advertiser") or {}
    failed = " ".join(r["rule_id"] for r in f.get("rules") or [] if r.get("result") == "fail")
    values = (f["id"], f["detected_at"], f["module"], f.get("risk_level"), f["score"], f["status"], f["platform"],
              f["title"], firm.get("name"), firm.get("registry_id"), adv.get("name"), adv.get("handle"), f["url"],
              failed, f.get("note"))
    return [_cell(v) for v in values]


def findings_csv(items: list[dict]) -> str:
    """UTF-8 BOM (so spreadsheets read Polish text right), a header row and one row per contract finding."""
    out = io.StringIO()
    out.write("﻿")
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    writer.writerows(_row(f) for f in items)
    return out.getvalue()
