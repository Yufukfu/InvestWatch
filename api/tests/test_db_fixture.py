"""The fixture itself: a throwaway database where the app role has CRUD on admin-created tables only."""

import psycopg
import pytest

from conftest import _plain


def test_app_role_gets_crud_on_admin_tables_but_no_ddl(empty_db):
    with psycopg.connect(_plain(empty_db.admin_url), autocommit=True) as admin:
        admin.execute("CREATE TABLE t (id int)")
    with psycopg.connect(_plain(empty_db.app_url), autocommit=True) as app:
        app.execute("INSERT INTO t VALUES (1)")
        assert app.execute("SELECT count(*) FROM t").fetchone()[0] == 1
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("CREATE TABLE u (id int)")


def test_fixture_refuses_a_remote_server(monkeypatch):
    from conftest import DatabaseFactory

    monkeypatch.delenv("TEST_DATABASE_ALLOW_REMOTE", raising=False)
    with pytest.raises(pytest.UsageError, match="localhost"):
        DatabaseFactory("postgresql://postgres:x@db.example.com:5432/postgres")


def test_fixture_repr_hides_urls(empty_db):
    assert "@" not in repr(empty_db)


def test_each_session_has_its_own_app_role(db_factory):
    import psycopg

    assert db_factory.app_role.startswith("iw_test_app_")
    db = db_factory.create()
    with psycopg.connect(_plain(db.app_url)) as app:
        assert app.execute("SELECT current_user").fetchone()[0] == db_factory.app_role
