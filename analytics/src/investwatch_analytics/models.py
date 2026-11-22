"""Contract v1 models (`.docs/integration-plan.md` §3, §4).

Input is lenient (unknown fields ignored, so provisional scraper fields never break us);
output is strict (unknown fields rejected). The JSON Schemas in `contracts/` stay the source of truth.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field

Platform = Literal["web", "facebook", "instagram", "tiktok", "youtube", "x", "forum", "other"]
SourceKind = Literal["firm_own", "third_party", "unknown"]
Module = Literal["M1", "M2", "M3"]
Severity = Literal["high", "medium", "low"]
Result = Literal["fail", "pass", "not_applicable", "uncertain"]
RegistryType = Literal["brokerage_house", "brokerage_bank", "foreign_branch", "foreign_no_branch"]

UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
RULE_ID_PATTERN = r"^(R([1-9]|1[0-8])|R12[ab]|S[13]\.[0-9]+)$"


def _absolute_http_url(value: str) -> str:
    """Contract `format: uri`, narrowed to absolute http(s) URLs; the value is kept verbatim."""
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname or any(c.isspace() or ord(c) < 0x20 for c in value):
        raise ValueError("must be an absolute http(s) URL")
    return value


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


HttpUrlStr = Annotated[str, AfterValidator(_absolute_http_url)]
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- input -------------------------------------------------------------------------------------


class Author(_Lenient):
    name: str | None = None
    handle: str | None = None
    profile_url: str | None = None
    followers: int | None = None


class Link(_Lenient):
    href: str
    text: str | None = None
    rel: str | None = None


class Block(_Lenient):
    viewport: Literal["desktop", "tablet", "mobile"]
    text: str
    font_size_px: float
    visible: bool
    tag: str | None = None
    font_weight: int | None = None
    color: str | None = None
    background_color: str | None = None
    bbox: list[float] | None = None
    in_viewport_on_load: bool | None = None
    requires_interaction: bool | None = None
    region: str | None = None
    overflow_clipped: bool | None = None


class ScrapedDocument(_Lenient):
    id: str = Field(pattern=UUID_PATTERN)
    platform: Platform
    source_kind: SourceKind
    url: HttpUrlStr
    fetched_at: AwareDatetime
    text: str
    source_id: str | None = None
    canonical_url: str | None = None
    published_at: datetime | None = None
    lang: str | None = None
    title: str | None = None
    content_hash: str | None = None
    author: Author | None = None
    links: list[Link] = Field(default_factory=list)
    blocks: list[Block] = Field(default_factory=list)


# ---- output ------------------------------------------------------------------------------------


Viewport = Literal["desktop", "tablet", "mobile"]


class EvidenceLocator(_Strict):
    """Where a visual rule's evidence sits on the rendered page (contract `rules[].evidence_locator`)."""

    viewport: Viewport | None = None
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)


class RuleResult(_Strict):
    rule_id: str = Field(pattern=RULE_ID_PATTERN)
    name: str
    result: Result
    severity: Severity
    evidence: str | None = None
    explanation: str | None = None
    legal_basis: str | None = None
    method: Literal["rule", "llm", "hybrid"] | None = None
    evidence_locator: EvidenceLocator | None = None


class FirmRef(_Strict):
    name: str
    registry_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    registry_type: RegistryType | None = None
    authorized: bool
    match_confidence: float = Field(ge=0, le=1)


class AdvertiserRef(_Strict):
    """Party publishing or offering the content (M1, M3). `in_registry` is required: the schema types it
    boolean, never null."""

    name: str | None = None
    handle: str | None = None
    profile_url: HttpUrlStr | None = None
    website: HttpUrlStr | None = None
    in_registry: bool
    on_warning_list: bool | None = None


class ModelInfo(_Strict):
    pipeline_version: str
    llm: str | None = None
    embedder: str | None = None


class Finding(_Strict):
    id: str = Field(pattern=UUID_PATTERN)
    document_id: str = Field(pattern=UUID_PATTERN)
    module: Module
    score: float = Field(ge=0, le=1)
    status: Literal["new", "in_review", "confirmed", "false_positive", "closed"] = "new"
    title: str
    summary: str | None = None
    firm: FirmRef | None = None
    advertiser: AdvertiserRef | None = None
    rules: list[RuleResult]
    content_excerpt: str | None = Field(default=None, max_length=500)
    url: HttpUrlStr
    platform: Platform
    note: str | None = None
    detected_at: UtcDatetime
    updated_at: UtcDatetime
    model: ModelInfo | None = None

    def to_contract(self) -> dict:
        """JSON-ready dict in contract shape (pydantic renders UTC timestamps with `Z`)."""
        return self.model_dump(mode="json")
