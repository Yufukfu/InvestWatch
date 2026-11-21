"""Gold-set evaluation command line (gold-set-evaluation spec, design decision 9).

    python -m investwatch_analytics.evaluation [--gold PATH] [--registry PATH] [--db] [--llm] [--module M2 ...]
    python analytics/eval/run.py ...   (same thing)

Rules-only and deterministic by default. stdout: the JSON report; stderr: JSON logs.
Exit codes: 0 ok; 1 a labeled module produced no finding (`not_run`) or a gold document failed analysis
(then nothing is stored);
2 invalid gold set, registry, catalogue or configuration (nothing analyzed, nothing written);
3 the run could not be stored (report still printed, nothing written).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .. import logging_setup
from ..registry import Registry, RegistryError
from ..rules.engine import CatalogueError
from ..storage import StoreError, StoreMisconfigured
from . import store
from .gold import GoldError, load_gold
from .known_ids import MODULES
from .runner import (
    DEFAULT_GOLD,
    DEFAULT_REGISTRY,
    THRESHOLDS_FILE,
    evaluate,
    load_build,
    report_json,
    write_thresholds,
)

log = logging.getLogger("investwatch_analytics.evaluation")


def _judge_factory():
    """`investwatch_analytics.llm.judge_from_env` once analytics-llm-p0 ships it, else None."""
    try:
        module = importlib.import_module("investwatch_analytics.llm")
    except ImportError:
        return None
    return getattr(module, "judge_from_env", None)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="investwatch_analytics.evaluation", description=__doc__.splitlines()[0])
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD, help=f"gold set (default {DEFAULT_GOLD.name})")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY,
                        help="firm registry CSV (default: the fictional eval registry)")
    parser.add_argument("--db", action="store_true", help="store the run in calibration_points (DATABASE_URL)")
    parser.add_argument("--llm", action="store_true", help="use the LLM judge from LLM_BASE_URL/LLM_MODEL/LLM_API_KEY")
    parser.add_argument("--module", action="append", choices=MODULES, help="evaluate only this module (repeatable)")
    parser.add_argument("--write-thresholds", nargs="?", type=Path, const=THRESHOLDS_FILE, default=None,
                        metavar="PATH", help="write the recommended thresholds (default eval/thresholds.json, ADR 0316)")
    return parser


def _fail(message: str, **extra) -> int:
    log.error(message, extra=extra)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        logging_setup.configure(os.environ.get("LOG_LEVEL", "INFO").upper(), stream=sys.stderr)
    except ValueError:
        logging_setup.configure("INFO", stream=sys.stderr)

    dsn = None
    if args.db:
        dsn = (os.environ.get("DATABASE_URL") or "").strip()
        if not dsn:
            return _fail("invalid configuration", error="DATABASE_URL is required for --db")
        try:
            store.check_dsn(dsn)
        except StoreMisconfigured as exc:
            return _fail("invalid configuration", error=str(exc))

    try:
        build = load_build()
        registry = Registry.from_csv(args.registry)
        items = load_gold(args.gold, build.catalogues)
        gold_sha256 = hashlib.sha256(Path(args.gold).read_bytes()).hexdigest()
    except GoldError as exc:
        for problem in exc.problems:
            log.error("invalid gold set", extra={"problem": problem})
        return 2
    except (RegistryError, CatalogueError) as exc:
        return _fail("invalid configuration", error=str(exc))

    if args.write_thresholds is not None and args.llm:
        return _fail("invalid configuration", error="--write-thresholds needs a rules-only run (ADR 0316)")

    judge = None
    if args.llm:
        if not (os.environ.get("LLM_BASE_URL") or "").strip():
            return _fail("invalid configuration", error="LLM_BASE_URL is required for --llm")
        factory = _judge_factory()
        if factory is None or not build.has_judge:
            return _fail("invalid configuration", error="no LLM judge in this build (analytics-llm-p0 not merged)")
        try:
            judge = factory()
        except Exception as exc:  # class only: a client error may quote the key or the endpoint
            return _fail("invalid configuration", error=f"LLM judge could not be built ({type(exc).__name__})")

    report = evaluate(items, registry=registry, build=build, now=datetime.now(timezone.utc),
                      gold_sha256=gold_sha256, judge=judge, modules=args.module)
    report["store"] = None
    code = 0
    if dsn is not None and report["run"]["analysis_errors"]:
        # A crashed gold document would be stored as false negatives: a bug, not a measurement.
        log.error("calibration run not stored", extra={"error": "gold documents failed analysis",
                                                       "gold_ids": report["run"]["analysis_errors"]})
    elif dsn is not None:
        try:
            report["store"] = store.write_run(dsn, report)
        except StoreError as exc:
            log.error("calibration run not stored", extra={"error": str(exc)})
            code = 3
    if args.write_thresholds is not None and report["run"]["analysis_errors"]:
        # Same reason as the store: zero scores from a crashed document would move the defaults.
        log.error("default thresholds not written", extra={"error": "gold documents failed analysis"})
    elif args.write_thresholds is not None:
        try:
            written = write_thresholds(args.write_thresholds, report)
        except (OSError, ValueError) as exc:  # JSONDecodeError is a ValueError
            return _fail("invalid configuration", error=f"thresholds file: {type(exc).__name__}: {exc}")
        log.info("default thresholds written", extra={"thresholds": written, "file": str(args.write_thresholds)})
    for module, entry in report["modules"].items():
        log.info("module evaluated", extra={"eval_module": module, "status": entry["status"],
                                            "labeled_samples": entry["labeled_samples"],
                                            "recommended_threshold": entry.get("recommended_threshold"),
                                            "default_threshold": entry.get("default_threshold"),
                                            "stored": (report["store"] or {}).get(module)})
    sys.stdout.write(report_json(report))
    if code:
        return code
    if report["run"]["analysis_errors"] or any(e["status"] == "not_run" for e in report["modules"].values()):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
