"""Fixtures for tests that need a real Postgres (design decision 10: SQLite is not a substitute).

Set TEST_DATABASE_ADMIN_URL to a superuser or CREATEDB+CREATEROLE connection on any database of a
Postgres 17 server, for example the one from api/README.md. Each test session creates its own
databases and drops them afterwards; without the variable the database tests are skipped.
"""

from __future__ import annotations

import json
import os
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import psycopg
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from psycopg import sql
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "contracts"
APP_ROLE = "iw_test_app"


def _plain(url: str) -> str:
    """psycopg.connect() wants a libpq URL without the SQLAlchemy driver suffix."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _sqlalchemy(url: str) -> str:
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


@dataclass(frozen=True)
class TestDatabase:
    name: str
    admin_url: str  # SQLAlchemy URL, admin role, this database
    app_url: str  # SQLAlchemy URL, least-privilege app role, this database


class DatabaseFactory:
    """Creates throwaway databases with the same grants as infra/postgres/init/01-app-role.sh."""

    def __init__(self, server_admin_url: str):
        self._server = make_url(_sqlalchemy(server_admin_url))
        self._app_password = secrets.token_hex(16)
        self._created: list[str] = []
        with self._connect() as conn:
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,)).fetchone()
            verb = "ALTER" if exists else "CREATE"
            conn.execute(sql.SQL(verb + " ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(
                sql.Identifier(APP_ROLE), sql.Literal(self._app_password)))

    def _connect(self, database: str | None = None) -> psycopg.Connection:
        url = self._server.set(database=database or self._server.database or "postgres")
        return psycopg.connect(_plain(url.render_as_string(hide_password=False)), autocommit=True)

    def create(self) -> TestDatabase:
        name = f"iw_test_{secrets.token_hex(4)}"
        with self._connect() as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        self._created.append(name)
        with self._connect(name) as conn:
            role, db = sql.Identifier(APP_ROLE), sql.Identifier(name)
            for stmt in (
                "REVOKE ALL ON DATABASE {db} FROM PUBLIC",
                "GRANT CONNECT, TEMPORARY ON DATABASE {db} TO {role}",
                "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
                "GRANT USAGE ON SCHEMA public TO {role}",
                "ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA public "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}",
                "ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA public "
                "GRANT USAGE, SELECT ON SEQUENCES TO {role}",
            ):
                conn.execute(sql.SQL(stmt).format(db=db, role=role))
        admin = self._server.set(database=name).render_as_string(hide_password=False)
        app = self._server.set(database=name, username=APP_ROLE, password=self._app_password)
        return TestDatabase(name, _sqlalchemy(admin), _sqlalchemy(app.render_as_string(hide_password=False)))

    def drop_all(self) -> None:
        with self._connect() as conn:
            for name in self._created:
                conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture(scope="session")
def db_factory() -> Iterator[DatabaseFactory]:
    url = os.environ.get("TEST_DATABASE_ADMIN_URL", "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_ADMIN_URL is not set (see api/README.md)")
    factory = DatabaseFactory(url)
    yield factory
    factory.drop_all()


@pytest.fixture
def empty_db(db_factory: DatabaseFactory) -> TestDatabase:
    """A fresh database with no tables, for migration tests."""
    return db_factory.create()


def contract_validator(name: str) -> Draft202012Validator:
    schema = json.loads((CONTRACTS_DIR / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def assert_contract_valid(name: str, instance) -> None:
    errors = [f"{'/'.join(map(str, e.path))}: {e.message}" for e in contract_validator(name).iter_errors(instance)]
    assert not errors, f"{name} schema violations: {errors}"


@pytest.fixture(scope="session")
def migrated_db(db_factory: DatabaseFactory) -> TestDatabase:
    """One migrated database per test session; app_engine empties it after every test."""
    from dbutil import upgrade

    db = db_factory.create()
    with pytest.MonkeyPatch.context() as mp:
        upgrade(mp, db.admin_url)
    return db


@pytest.fixture
def app_engine(migrated_db: TestDatabase):
    """SQLAlchemy engine as the least-privilege app role, on empty tables."""
    from sqlalchemy import create_engine, text

    engine = create_engine(migrated_db.app_url)
    yield engine
    with engine.begin() as conn:
        for table in ("findings", "documents", "job_errors", "sources", "calibration_points"):
            conn.execute(text(f"DELETE FROM {table}"))
    engine.dispose()
