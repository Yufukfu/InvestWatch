"""Requirement 'Migrations own the schema' (specs/database-schema)."""

import psycopg
import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from conftest import _plain
from dbutil import TABLES, alembic_config, downgrade, upgrade


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _current(url: str) -> str | None:
    with psycopg.connect(_plain(url)) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        return row[0] if row else None


def test_empty_database_is_migrated(monkeypatch, empty_db):
    upgrade(monkeypatch, empty_db.admin_url)
    assert set(TABLES) <= _tables(empty_db.admin_url)
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    assert _current(empty_db.admin_url) == head


def test_migration_is_idempotent(monkeypatch, empty_db):
    upgrade(monkeypatch, empty_db.admin_url)
    before = _tables(empty_db.admin_url)
    upgrade(monkeypatch, empty_db.admin_url)
    assert _tables(empty_db.admin_url) == before


def test_downgrade_removes_the_tables(monkeypatch, empty_db):
    upgrade(monkeypatch, empty_db.admin_url)
    downgrade(monkeypatch, empty_db.admin_url)
    assert not (set(TABLES) & _tables(empty_db.admin_url))
    upgrade(monkeypatch, empty_db.admin_url)
    assert set(TABLES) <= _tables(empty_db.admin_url)


def test_models_match_the_migrations(monkeypatch, empty_db):
    """`alembic check` finds no difference in tables, columns, types, nullability, indexes and unique
    constraints between db/tables.py and the migrated database. It does not diff CHECK constraints:
    test_enum_checks_match_the_contracts and the rejection tests in test_constraints.py cover those."""
    upgrade(monkeypatch, empty_db.admin_url)
    command.check(alembic_config())


def test_migration_refuses_without_admin_url(monkeypatch):
    monkeypatch.delenv("DATABASE_ADMIN_URL", raising=False)
    with pytest.raises(Exception, match="DATABASE_ADMIN_URL"):
        command.upgrade(alembic_config(), "head")


CRUD = {
    "sources": ("INSERT INTO sources (id, name, platform, url, source_kind, target_modules) "
                "VALUES (gen_random_uuid(), 'a', 'web', 'https://a.example', 'unknown', '{M1}')"),
    "documents": ("INSERT INTO documents (id, platform, source_kind, url, fetched_at, text) "
                  "VALUES (gen_random_uuid(), 'web', 'unknown', 'https://a.example', now(), 't')"),
    "job_errors": "INSERT INTO job_errors (id, reason) VALUES (gen_random_uuid(), 'blocked')",
    "calibration_points": ("INSERT INTO calibration_points (run_id, module, threshold, tp, fp, fn, tn, "
                           "precision, recall, labeled_samples, computed_at) "
                           "VALUES (gen_random_uuid(), 'M2', 0.5, 1, 1, 1, 1, 0.5, 0.5, 4, now())"),
}


def test_application_role_has_crud_but_no_ddl(monkeypatch, empty_db):
    upgrade(monkeypatch, empty_db.admin_url)
    with psycopg.connect(_plain(empty_db.app_url), autocommit=True) as app:
        for table, insert in CRUD.items():
            app.execute(insert)
            app.execute(f"UPDATE {table} SET id = id")
            assert app.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 1
        doc = app.execute("SELECT id FROM documents").fetchone()[0]
        app.execute("INSERT INTO findings (id, document_id, module, score, title, url, platform, detected_at, "
                    "updated_at) VALUES (gen_random_uuid(), %s, 'M2', 0.5, 't', 'https://a.example', 'web', "
                    "now(), now())", (doc,))
        for table in ("findings", *CRUD):
            app.execute(f"DELETE FROM {table}")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("CREATE TABLE x (id int)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("ALTER TABLE documents ADD COLUMN x int")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("UPDATE alembic_version SET version_num = 'x'")


def test_0003_text_check_is_reversible(monkeypatch, empty_db):
    """Downgrading 0003 removes only the non-empty text check; upgrading puts it back."""
    upgrade(monkeypatch, empty_db.admin_url)
    downgrade(monkeypatch, empty_db.admin_url, "0002")
    assert "ck_documents_text_not_empty" not in _checks(empty_db.admin_url)
    upgrade(monkeypatch, empty_db.admin_url)
    assert "ck_documents_text_not_empty" in _checks(empty_db.admin_url)


def _checks(url: str) -> set[str]:
    with psycopg.connect(_plain(url)) as conn:
        return {r[0] for r in conn.execute("SELECT conname FROM pg_constraint WHERE contype = 'c'")}
