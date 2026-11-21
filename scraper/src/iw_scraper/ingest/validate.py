import json
from functools import lru_cache

from jsonschema import Draft202012Validator, FormatChecker

from iw_scraper.config import contracts_dir
from iw_scraper.types import JobError, Reason

_SCHEMA_FILE = "schemas/scraped-document.schema.json"
_MAX_DETAIL = 300


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads((contracts_dir() / _SCHEMA_FILE).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _invalid(doc: dict, detail: str) -> JobError:
    source_id = doc.get("source_id")
    return JobError(Reason.SCHEMA_INVALID, detail[:_MAX_DETAIL], source_id if isinstance(source_id, str) else None)


def check_document(doc: dict) -> JobError | None:
    """`None` when the document is a valid ScrapedDocument v1 with a `source_id`, else a `schema_invalid` error.

    The schema allows a null `source_id` (ad-hoc URLs), but the dedup index cannot cover NULLs, so the
    scraper never ingests without one.
    """
    errors = sorted(_validator().iter_errors(doc), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        where = "/".join(str(part) for part in first.absolute_path) or "(document)"
        return _invalid(doc, f"{where}: {first.validator} failed")
    if not doc.get("source_id"):
        return _invalid(doc, "source_id: required for collected documents")
    return None
