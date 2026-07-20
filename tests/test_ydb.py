"""Тест подключения к YDB.

Запуск:
    uv run python -m pytest tests/test_ydb.py -v

Тесты пропускаются, если YDB_ENDPOINT/YDB_DATABASE не заданы.
Для локальной проверки создайте .env файл (см. .env.example).
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest

from src import ydb_repository

TEST_THING = "wrench"
TEST_PLACE = "toolbox"
TEST_PREPOSITION = "in"


def _ydb_configured() -> bool:
    return bool(os.getenv("YDB_ENDPOINT")) and bool(os.getenv("YDB_DATABASE"))


requires_ydb = pytest.mark.skipif(
    not _ydb_configured(),
    reason="YDB_ENDPOINT / YDB_DATABASE not set",
)


@pytest.fixture
def no_ydb_env() -> Generator[None, None, None]:
    """Временно отключить YDB окружение для тестов."""
    saved_ep = ydb_repository.YDB_ENDPOINT
    saved_db = ydb_repository.YDB_DATABASE
    saved_pool = ydb_repository._pool
    ydb_repository.YDB_ENDPOINT = ""
    ydb_repository.YDB_DATABASE = ""
    ydb_repository._pool = None
    try:
        yield
    finally:
        ydb_repository.YDB_ENDPOINT = saved_ep
        ydb_repository.YDB_DATABASE = saved_db
        ydb_repository._pool = saved_pool


class TestYDBConnection:
    """Базовая проверка подключения."""

    @requires_ydb
    def test_driver_initializes(self):
        """Driver should initialize successfully."""
        pool = ydb_repository._ensure_pool()
        assert pool is not None, "Session pool should be created"

    @requires_ydb
    def test_is_available(self):
        """YDB should be available."""
        assert ydb_repository.is_available(), "YDB should be available"

    @requires_ydb
    def test_simple_query(self):
        """Simple query should return results."""
        pool = ydb_repository._ensure_pool()
        assert pool is not None
        rows = pool.execute_with_retries("SELECT 1 AS test_value")
        assert rows[0].rows[0].test_value == 1


class TestYDBTable:
    """Проверка работы с таблицей items."""

    TEST_USER = "__test_user_ydb_check__"

    @requires_ydb
    def test_upsert_and_load(self):
        """Upsert and load an item."""
        repo = ydb_repository.YdbItemsRepository()
        repo.upsert_item(self.TEST_USER, TEST_THING, TEST_PLACE)
        stored = repo.load_items(self.TEST_USER)
        assert TEST_THING in stored
        assert stored[TEST_THING] == (TEST_PREPOSITION, TEST_PLACE)

    @requires_ydb
    def test_upsert_updates(self):
        """Upsert should update existing item."""
        repo = ydb_repository.YdbItemsRepository()
        repo.upsert_item(self.TEST_USER, TEST_THING, "new_place")
        stored = repo.load_items(self.TEST_USER)
        assert stored[TEST_THING] == (TEST_PREPOSITION, "new_place")

    @requires_ydb
    def test_load_empty_user(self):
        """Load items for empty user."""
        repo = ydb_repository.YdbItemsRepository()
        stored = repo.load_items("__nonexistent_user_12345__")
        assert stored == {}

    @requires_ydb
    def test_delete(self):
        """Delete an item."""
        repo = ydb_repository.YdbItemsRepository()
        repo.upsert_item(self.TEST_USER, "to_delete", "somewhere")
        repo.delete_item(self.TEST_USER, "to_delete")
        stored = repo.load_items(self.TEST_USER)
        assert "to_delete" not in stored

    @requires_ydb
    def test_multiple_items(self):
        """Handle multiple items."""
        repo = ydb_repository.YdbItemsRepository()
        repo.upsert_item(self.TEST_USER, "item_a", "place_a")
        repo.upsert_item(self.TEST_USER, "item_b", "place_b")
        stored = repo.load_items(self.TEST_USER)
        assert stored["item_a"] == ("in", "place_a")
        assert stored["item_b"] == ("in", "place_b")
        repo.delete_item(self.TEST_USER, "item_a")
        repo.delete_item(self.TEST_USER, "item_b")


class TestYDBWithoutEnv:
    """Проверка поведения без YDB (локальная разработка)."""

    def test_is_available_returns_false(self, no_ydb_env: None) -> None:
        """is_available should return False without YDB config."""
        assert not ydb_repository.is_available()

    def test_load_items_returns_empty(self, no_ydb_env: None) -> None:
        """load_items should return empty dict without YDB config."""
        repo = ydb_repository.YdbItemsRepository()
        assert repo.load_items("any_user") == {}
