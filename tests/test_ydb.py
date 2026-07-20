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
TEST_KEY = "test_thing#"


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
    def test_upsert_and_find(self):
        """Upsert and find an item by canonical key."""
        repo = ydb_repository.YdbItemsRepository()
        repo.upsert_item(self.TEST_USER, TEST_KEY, TEST_THING, TEST_PLACE, "лежит")
        rec = repo.find_by_canonical_key(self.TEST_USER, TEST_KEY)
        assert rec is not None
        assert rec.display_name == TEST_THING
        assert rec.location == TEST_PLACE
        assert rec.verb == "лежит"

    @requires_ydb
    def test_upsert_updates(self):
        """Upsert should update existing item."""
        repo = ydb_repository.YdbItemsRepository()
        repo.upsert_item(self.TEST_USER, TEST_KEY, TEST_THING, "new_place", "лежит")
        rec = repo.find_by_canonical_key(self.TEST_USER, TEST_KEY)
        assert rec is not None
        assert rec.location == "new_place"

    @requires_ydb
    def test_list_empty_user(self):
        """List display names for empty user."""
        repo = ydb_repository.YdbItemsRepository()
        names = repo.list_display_names("__nonexistent_user_12345__")
        assert names == []

    @requires_ydb
    def test_delete(self):
        """Delete an item."""
        repo = ydb_repository.YdbItemsRepository()
        repo.upsert_item(self.TEST_USER, "to_delete#", "to_delete", "somewhere", "лежит")
        repo.delete_item(self.TEST_USER, "to_delete#")
        rec = repo.find_by_canonical_key(self.TEST_USER, "to_delete#")
        assert rec is None

    @requires_ydb
    def test_multiple_items(self):
        """Handle multiple items."""
        repo = ydb_repository.YdbItemsRepository()
        repo.upsert_item(self.TEST_USER, "item_a#", "item_a", "place_a", "лежит")
        repo.upsert_item(self.TEST_USER, "item_b#", "item_b", "place_b", "лежит")
        rec_a = repo.find_by_canonical_key(self.TEST_USER, "item_a#")
        rec_b = repo.find_by_canonical_key(self.TEST_USER, "item_b#")
        assert rec_a is not None
        assert rec_a.location == "place_a"
        assert rec_b is not None
        assert rec_b.location == "place_b"
        repo.delete_item(self.TEST_USER, "item_a#")
        repo.delete_item(self.TEST_USER, "item_b#")


class TestYDBWithoutEnv:
    """Проверка поведения без YDB (локальная разработка)."""

    def test_is_available_returns_false(self, no_ydb_env: None) -> None:
        """is_available should return False without YDB config."""
        assert not ydb_repository.is_available()

    def test_list_display_names_returns_empty(self, no_ydb_env: None) -> None:
        """list_display_names should return empty list without YDB config."""
        repo = ydb_repository.YdbItemsRepository()
        assert repo.list_display_names("any_user") == []
