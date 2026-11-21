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
