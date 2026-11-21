"""`python -m investwatch_analytics.knf`: refresh `registry/knf.csv` from the KNF lists, by hand only.

Exit 0 with a summary on success; exit 1 with the reason (`fetch_failed`, `list_moved`, `layout_changed`,
`count_dropped`, `invalid_output`, `manual_row`) and the old files untouched on failure. Logs are JSON on stdout.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .. import logging_setup
from ..config import SEED_REGISTRY
from . import KnfError
from .build import build, load_manual
from .fetch import Fetcher, HttpFetcher, fetch_all
from .write import check_counts, read_meta, read_previous, render_csv, render_meta, summarize, write_registry

log = logging.getLogger("investwatch_analytics.knf")
REGISTRY_DIR = Path(__file__).resolve().parents[3] / "registry"


def main(argv: Sequence[str] | None = None, *, fetcher: Fetcher | None = None,
         now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> int:
    parser = argparse.ArgumentParser(prog="python -m investwatch_analytics.knf", description=__doc__)
    parser.add_argument("--out", type=Path, default=REGISTRY_DIR / "knf.csv")
    parser.add_argument("--previous", type=Path, default=None,
                        help="registry whose ids are kept (default: --out when it exists)")
    parser.add_argument("--manual", type=Path, default=REGISTRY_DIR / "knf_domains_manual.csv")
    parser.add_argument("--accept-drop", action="store_true",
                        help="write even if a list lost more than half of its records")
    parser.add_argument("--verbose", action="store_true", help="log every dropped alias and domain")
    args = parser.parse_args(argv)
    logging_setup.configure("INFO")

    out = args.out.resolve()
    if out == SEED_REGISTRY.resolve():
        log.error("knf load failed", extra={"reason": "invalid_output",
                                            "error": "refusing to overwrite the fictional seed registry"})
        return 1
    try:
        previous_path = args.previous or out
        previous = read_previous(previous_path)
        previous_meta = read_meta(previous_path)
        manual = load_manual(args.manual)
        fetched = fetch_all(fetcher or HttpFetcher())
        check_counts(fetched, previous_meta, accept_drop=args.accept_drop)
        firms, report = build(fetched, previous={k: v[0] for k, v in previous.items()}, manual=manual)
        summary = summarize(firms, report, previous)
        write_registry(out, render_csv(firms), render_meta(fetched, firms, summary, now()))
    except KnfError as exc:
        log.error("knf load failed", extra={"reason": exc.reason, "error": exc.message})
        return 1
    if args.verbose:
        for firm, alias, reason in report.dropped_aliases:
            log.info("alias dropped", extra={"firm": firm, "alias": alias, "reason": reason})
        for domain, reason in report.dropped_domains:
            log.info("domain dropped", extra={"domain": domain, "reason": reason})
    log.info("knf registry written", extra={"out": str(out), **asdict(summary)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
