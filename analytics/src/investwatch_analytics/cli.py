"""Analyze documents from a JSON file without any infrastructure.

    python -m investwatch_analytics.cli <file.json>

The file holds one ScrapedDocument or a list of them. Findings are written to stdout as a JSON
list (contract shape); logs go to stderr as JSON so stdout stays machine-readable.
Each document is validated on its own: an invalid one is logged (index, error locations and types,
never input values) and skipped.
If analyzing one document raises, that document is logged (id and exception type only) and
skipped; the other documents' findings are still written.
Exit codes: 0 ok; 1 at least one document failed analysis (stdout holds the others' findings);
2 unreadable input, bad configuration, or documents of which none is valid (nothing on stdout).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from pydantic import ValidationError

from . import logging_setup
from .config import ConfigError, LlmSettings, Settings, official_source_domains
from .llm import build_judge
from .models import ScrapedDocument
from .pipeline import analyze, default_signal_catalogues
from .registry import Registry, RegistryError
from .rules.engine import Catalogue, CatalogueError

log = logging.getLogger("investwatch_analytics.cli")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="investwatch_analytics.cli", description=__doc__.splitlines()[0])
    parser.add_argument("file", type=Path, help="JSON file with one ScrapedDocument or a list of them")
    parser.add_argument("--no-llm", action="store_true", help="rules-only, even when LLM_BASE_URL is set")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    try:
        logging_setup.configure(settings.log_level, stream=sys.stderr)
    except ValueError as exc:
        logging_setup.configure("INFO", stream=sys.stderr)
        log.error("invalid configuration", extra={"error": f"LOG_LEVEL: {exc}"})
        return 2

    try:
        llm_settings = LlmSettings.from_env()
        official_source_domains()  # routing reads it per document: a bad value stops here, not per document
    except ConfigError as exc:
        log.error("invalid configuration", extra={"error": str(exc)})
        return 2
    judge = None if args.no_llm else build_judge(llm_settings)  # no Redis here: the CLI never caches
    try:
        registry = Registry.from_csv(settings.registry_csv)
        catalogue = Catalogue.load()
        signals = default_signal_catalogues()  # M1/M3 catalogues: a bad YAML fails here, not per document
        raw = json.loads(args.file.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        log.error("cannot read input", extra={"file": str(args.file), "error": str(exc)})
        return 2
    except (RegistryError, CatalogueError) as exc:
        log.error("invalid configuration", extra={"error": str(exc)})
        return 2

    items = raw if isinstance(raw, list) else [raw]
    docs = [doc for index, item in enumerate(items) if (doc := _validate(item, index, args.file)) is not None]
    if items and not docs:
        log.error("no valid document", extra={"file": str(args.file), "documents": len(items)})
        return 2

    findings: list[dict] = []
    failed = 0
    for doc in docs:
        try:
            findings.extend(f.to_contract() for f in analyze(doc, registry=registry, catalogue=catalogue,
                                                             signals=signals, judge=judge))
        except Exception as exc:  # one bad document must not cost the batch; a bug still shows in the exit code
            failed += 1
            # Type only: exception messages can carry scraped text.
            log.error("analysis failed", extra={"document_id": doc.id, "error_type": type(exc).__name__})
    # The findings JSON is UTF-8 whatever the console code page (cp1250 on Windows cannot encode an emoji).
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(json.dumps(findings, ensure_ascii=False, indent=2) + "\n")
    return 1 if failed else 0


def _validate(item: object, index: int, file: Path) -> ScrapedDocument | None:
    try:
        return ScrapedDocument.model_validate(item)
    except ValidationError as exc:
        # Only where and what kind: `str(exc)` and the default errors() embed the scraped input.
        errors = [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors(include_input=False, include_url=False)]
        log.warning("invalid document", extra={"file": str(file), "index": index, "errors": errors})
        return None


if __name__ == "__main__":
    sys.exit(main())
