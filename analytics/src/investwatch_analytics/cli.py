"""Analyze documents from a JSON file without any infrastructure.

    python -m investwatch_analytics.cli <file.json>

The file holds one ScrapedDocument or a list of them. Findings are written to stdout as a JSON
list (contract shape); logs go to stderr as JSON so stdout stays machine-readable.
Exit codes: 0 ok, 2 bad input or configuration (nothing is written to stdout).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from pydantic import ValidationError

from . import logging_setup
from .config import Settings
from .models import ScrapedDocument
from .pipeline import analyze
from .registry import Registry, RegistryError
from .rules.engine import Catalogue, CatalogueError

log = logging.getLogger("investwatch_analytics.cli")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="investwatch_analytics.cli", description=__doc__.splitlines()[0])
    parser.add_argument("file", type=Path, help="JSON file with one ScrapedDocument or a list of them")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    logging_setup.configure(settings.log_level, stream=sys.stderr)

    try:
        registry = Registry.from_csv(settings.registry_csv)
        catalogue = Catalogue.load()
        raw = json.loads(args.file.read_text(encoding="utf-8"))
        items = raw if isinstance(raw, list) else [raw]
        docs = [ScrapedDocument.model_validate(item) for item in items]
    except (OSError, json.JSONDecodeError) as exc:
        log.error("cannot read input", extra={"file": str(args.file), "error": str(exc)})
        return 2
    except ValidationError as exc:
        log.error("invalid document", extra={"file": str(args.file), "error": str(exc)})
        return 2
    except (RegistryError, CatalogueError) as exc:
        log.error("invalid configuration", extra={"error": str(exc)})
        return 2

    findings = [f.to_contract() for doc in docs for f in analyze(doc, registry=registry, catalogue=catalogue)]
    sys.stdout.write(json.dumps(findings, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
