"""Тест подключения к YDB.

Запуск:
    uv run python -m pytest tests/test_ydb.py -v

Тесты пропускаются, если YDB_ENDPOINT/YDB_DATABASE не заданы.
Для локальной проверки создайте .env файл (см. .env.example).
"""

from __future__ import annotations

import os

import pytest

import db


def _ydb_configured() -> bool:
    return bool(os.getenv("YDB_ENDPOINT")) and bool(os.getenv("YDB_DATABASE"))


requires_ydb = pytest.mark.skipif(
    not _ydb_configured(),
    reason="YDB_ENDPOINT / YDB_DATABASE not set",
)


class TestYDBConnection:
    """Базовая проверка подключения."""

    @requires_ydb
    def test_driver_initializes(self):
        pool = db._ensure_driver()
        assert pool is not None, "Session pool should be created"

    @requires_ydb
    def test_is_available(self):
        assert db.is_available(), "YDB should be available"

    @requires_ydb
    def test_simple_query(self):
        pool = db._ensure_driver()
        assert pool is not None

        def _test(session):
            res = session.transaction().execute(
                "SELECT 1 AS test_value",
                commit_tx=True,
            )
            assert res[0].rows[0].test_value == 1

        pool.retry_operation_sync(_test)


class TestYDBTable:
    """Проверка работы с таблицей items."""

    TEST_USER = "__test_user_ydb_check__"

    @requires_ydb
    def test_upsert_and_load(self):
        db.upsert_item(self.TEST_USER, "test_thing", "test_place")
        items = db.load_items(self.TEST_USER)
        assert "test_thing" in items
        assert items["test_thing"] == "test_place"

    @requires_ydb
    def test_upsert_updates(self):
        db.upsert_item(self.TEST_USER, "test_thing", "new_place")
        items = db.load_items(self.TEST_USER)
        assert items["test_thing"] == "new_place"

    @requires_ydb
    def test_load_empty_user(self):
        items = db.load_items("__nonexistent_user_12345__")
        assert items == {}

    @requires_ydb
    def test_delete(self):
        db.upsert_item(self.TEST_USER, "to_delete", "somewhere")
        db.delete_item(self.TEST_USER, "to_delete")
        items = db.load_items(self.TEST_USER)
        assert "to_delete" not in items

    @requires_ydb
    def test_multiple_items(self):
        db.upsert_item(self.TEST_USER, "item_a", "place_a")
        db.upsert_item(self.TEST_USER, "item_b", "place_b")
        items = db.load_items(self.TEST_USER)
        assert items["item_a"] == "place_a"
        assert items["item_b"] == "place_b"
        # Cleanup
        db.delete_item(self.TEST_USER, "item_a")
        db.delete_item(self.TEST_USER, "item_b")


class TestYDBWithoutEnv:
    """Проверка поведения без YDB (локальная разработка)."""

    def test_is_available_returns_false(self):
        old_ep = db.YDB_ENDPOINT
        old_db = db.YDB_DATABASE
        db.YDB_ENDPOINT = ""
        db.YDB_DATABASE = ""
        # Reset pool
        old_pool = db._pool
        db._pool = None
        try:
            assert not db.is_available()
        finally:
            db.YDB_ENDPOINT = old_ep
            db.YDB_DATABASE = old_db
            db._pool = old_pool

    def test_load_items_returns_empty(self):
        old_ep = db.YDB_ENDPOINT
        old_db = db.YDB_DATABASE
        db.YDB_ENDPOINT = ""
        db.YDB_DATABASE = ""
        old_pool = db._pool
        db._pool = None
        try:
            assert db.load_items("any_user") == {}
        finally:
            db.YDB_ENDPOINT = old_ep
            db.YDB_DATABASE = old_db
            db._pool = old_pool
