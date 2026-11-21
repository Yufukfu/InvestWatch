import json
from functools import lru_cache
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from iw_scraper.config import contracts_dir
from iw_scraper.ingest.document import normalise_text
from iw_scraper.types import JobError, Reason

_SCHEMA_FILE = "schemas/scraped-document.schema.json"
_MAX_DETAIL = 300
_WEB_SCHEMES = frozenset({"http", "https"})


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads((contracts_dir() / _SCHEMA_FILE).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _invalid(doc: dict, detail: str) -> JobError:
    source_id = doc.get("source_id")
    return JobError(Reason.SCHEMA_INVALID, detail[:_MAX_DETAIL], source_id if isinstance(source_id, str) else None)


def _url_fields(doc: dict) -> list[tuple[str, str]]:
    author = doc.get("author")
    candidates = [("url", doc.get("url")), ("canonical_url", doc.get("canonical_url"))]
    if isinstance(author, dict):
        candidates.append(("author/profile_url", author.get("profile_url")))
    return [(name, value) for name, value in candidates if isinstance(value, str)]


def _unusable_url(doc: dict) -> str | None:
    """A URL the schema lets through but the readers must not get: `format: uri` only checks syntax, and
    `javascript:alert(1)` conforms to it."""
    for name, value in _url_fields(doc):
        if urlsplit(value).scheme.lower() not in _WEB_SCHEMES:
            return f"{name}: scheme must be http or https"
    return None


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
    bad = _unusable_url(doc)
    if bad is not None:
        return _invalid(doc, bad)
    if not doc.get("source_id"):
        return _invalid(doc, "source_id: required for collected documents")
    if not normalise_text(doc["text"]):
        # the schema allows "", but a blank page must surface as an error, not as one junk row per source
        return JobError(Reason.EMPTY_TEXT, "text is blank after normalisation", doc["source_id"])
    return None
