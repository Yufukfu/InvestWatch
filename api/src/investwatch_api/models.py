"""Request bodies of contracts/openapi.yaml. Copied from the archived mock server (design decision 2)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictFloat, StrictInt, field_validator, model_validator

Module = Literal["M1", "M2", "M3"]
RiskLevel = Literal["high", "medium", "low"]
Viewport = Literal["desktop", "tablet", "mobile"]
Platform = Literal["web", "facebook", "instagram", "tiktok", "youtube", "x", "forum", "other"]
SourceKind = Literal["firm_own", "third_party", "unknown"]
Status = Literal["new", "in_review", "confirmed", "false_positive", "closed"]
STATUSES = ("new", "in_review", "confirmed", "false_positive", "closed")

_Unit = StrictFloat | StrictInt


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FindingPatch(_Strict):
    status: Status | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_fields_set:
            raise ValueError("at least one of status, note is required")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self


class Thresholds(_Strict):
    M1: _Unit = Field(ge=0, le=1)
    M2: _Unit = Field(ge=0, le=1)
    M3: _Unit = Field(ge=0, le=1)


def _unique_modules(value):
    if value is not None and len(set(value)) != len(value):
        raise ValueError("target_modules must not repeat a module")  # contract: uniqueItems
    return value


class SourceCreate(_Strict):
    name: str = Field(min_length=1)
    platform: Platform
    url: HttpUrl
    source_kind: SourceKind
    target_modules: list[Module] = Field(min_length=1)
    schedule_cron: str | None = None
    active: bool = True

    _modules = field_validator("target_modules")(_unique_modules)


class SourcePatch(_Strict):
    name: str | None = Field(default=None, min_length=1)
    platform: Platform | None = None
    url: HttpUrl | None = None
    source_kind: SourceKind | None = None
    target_modules: list[Module] | None = Field(default=None, min_length=1)
    schedule_cron: str | None = None
    active: bool | None = None

    _modules = field_validator("target_modules")(_unique_modules)

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        nulls = [k for k in self.model_fields_set if getattr(self, k) is None and k != "schedule_cron"]
        if nulls:
            raise ValueError(f"cannot be null: {', '.join(sorted(nulls))}")
        return self


class ScanRequest(_Strict):
    source_id: UUID
