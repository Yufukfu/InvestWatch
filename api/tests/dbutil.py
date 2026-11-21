"""Helpers for database tests: alembic runner and valid sample rows."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config

API_DIR = Path(__file__).resolve().parents[1]
TABLES = ("sources", "documents", "findings", "job_errors", "calibration_points")


def alembic_config() -> Config:
    return Config(str(API_DIR / "alembic.ini"))


def upgrade(monkeypatch, admin_url: str, revision: str = "head") -> None:
    monkeypatch.setenv("DATABASE_ADMIN_URL", admin_url)
    command.upgrade(alembic_config(), revision)


def downgrade(monkeypatch, admin_url: str, revision: str = "base") -> None:
    monkeypatch.setenv("DATABASE_ADMIN_URL", admin_url)
    command.downgrade(alembic_config(), revision)


def now() -> datetime:
    return datetime.now(timezone.utc)


def source_row(**over) -> dict:
    row = dict(id=uuid.uuid4(), name="Alfa", platform="web", url="https://alfa.example/",
               source_kind="firm_own", target_modules=["M2"], active=True)
    row.update(over)
    return row


def document_row(**over) -> dict:
    row = dict(id=uuid.uuid4(), source_id=None, platform="web", source_kind="firm_own",
               url="https://alfa.example/oferta", fetched_at=now(), text="Zarabiaj 20% rocznie.",
               content_hash=uuid.uuid4().hex * 2, payload={})
    row.update(over)
    return row


def finding_row(document_id, **over) -> dict:
    t = now()
    row = dict(id=uuid.uuid4(), document_id=document_id, module="M2", score=0.8, status="new",
               title="Brak ostrzeżenia o ryzyku", url="https://alfa.example/oferta", platform="web",
               rules=[], detected_at=t, updated_at=t)
    row.update(over)
    return row
