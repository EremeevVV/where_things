"""Тест подключения к YDB.

Запуск:
    uv run python -m pytest tests/test_ydb.py -v

Тесты пропускаются, если YDB_ENDPOINT/YDB_DATABASE не заданы.
Для локальной проверки создайте .env файл (см. .env.example).
"""

from __future__ import annotations

import os

import pytest

import ydb_repository


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
        pool = ydb_repository._ensure_pool()
        assert pool is not None, "Session pool should be created"

    @requires_ydb
    def test_is_available(self):
        assert ydb_repository.is_available(), "YDB should be available"

    @requires_ydb
    def test_simple_query(self):
        pool = ydb_repository._ensure_pool()
        assert pool is not None
        result = pool.execute_with_retries("SELECT 1 AS test_value")
        assert result[0].rows[0].test_value == 1


class TestYDBTable:
    """Проверка работы с таблицей items."""

    TEST_USER = "__test_user_ydb_check__"

    @requires_ydb
    def test_upsert_and_load(self):
        repo = ydb_repository.YdbItemsRepository()
        repo.upsert_item(self.TEST_USER, "test_thing", "test_place")
        items = repo.load_items(self.TEST_USER)
        assert "test_thing" in items
        assert items["test_thing"] == "test_place"

    @requires_ydb
    def test_upsert_updates(self):
        repo = ydb_repository.YdbItemsRepository()
        repo.upsert_item(self.TEST_USER, "test_thing", "new_place")
        items = repo.load_items(self.TEST_USER)
        assert items["test_thing"] == "new_place"

    @requires_ydb
    def test_load_empty_user(self):
        repo = ydb_repository.YdbItemsRepository()
        items = repo.load_items("__nonexistent_user_12345__")
        assert items == {}

    @requires_ydb
    def test_delete(self):
        repo = ydb_repository.YdbItemsRepository()
        repo.upsert_item(self.TEST_USER, "to_delete", "somewhere")
        repo.delete_item(self.TEST_USER, "to_delete")
        items = repo.load_items(self.TEST_USER)
        assert "to_delete" not in items

    @requires_ydb
    def test_multiple_items(self):
        repo = ydb_repository.YdbItemsRepository()
        repo.upsert_item(self.TEST_USER, "item_a", "place_a")
        repo.upsert_item(self.TEST_USER, "item_b", "place_b")
        items = repo.load_items(self.TEST_USER)
        assert items["item_a"] == "place_a"
        assert items["item_b"] == "place_b"
        # Cleanup
        repo.delete_item(self.TEST_USER, "item_a")
        repo.delete_item(self.TEST_USER, "item_b")


class TestYDBWithoutEnv:
    """Проверка поведения без YDB (локальная разработка)."""

    def test_is_available_returns_false(self):
        old_ep = ydb_repository.YDB_ENDPOINT
        old_db = ydb_repository.YDB_DATABASE
        ydb_repository.YDB_ENDPOINT = ""
        ydb_repository.YDB_DATABASE = ""
        # Reset pool
        old_pool = ydb_repository._pool
        ydb_repository._pool = None
        try:
            assert not ydb_repository.is_available()
        finally:
            ydb_repository.YDB_ENDPOINT = old_ep
            ydb_repository.YDB_DATABASE = old_db
            ydb_repository._pool = old_pool

    def test_load_items_returns_empty(self):
        old_ep = ydb_repository.YDB_ENDPOINT
        old_db = ydb_repository.YDB_DATABASE
        ydb_repository.YDB_ENDPOINT = ""
        ydb_repository.YDB_DATABASE = ""
        old_pool = ydb_repository._pool
        ydb_repository._pool = None
        try:
            repo = ydb_repository.YdbItemsRepository()
            assert repo.load_items("any_user") == {}
        finally:
            ydb_repository.YDB_ENDPOINT = old_ep
            ydb_repository.YDB_DATABASE = old_db
            ydb_repository._pool = old_pool
