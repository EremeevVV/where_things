from __future__ import annotations

import datetime
import os

import ydb
import ydb.iam

# ── YDB driver + query pool (module level — reused across warm invocations) ──

_driver: ydb.Driver | None = None
_pool: ydb.QuerySessionPool | None = None

YDB_ENDPOINT = os.getenv("YDB_ENDPOINT", "")
YDB_DATABASE = os.getenv("YDB_DATABASE", "")

# ── SQL ───────────────────────────────────────────────────────────────────────

UPSERT_SQL = """
DECLARE $user_id AS Utf8;
DECLARE $name AS Utf8;
DECLARE $place AS Utf8;
DECLARE $updated_at AS Timestamp;
UPSERT INTO items (user_id, name, place, updated_at)
VALUES ($user_id, $name, $place, $updated_at);
"""

SELECT_ALL_SQL = """
DECLARE $user_id AS Utf8;
SELECT name, place FROM items WHERE user_id = $user_id;
"""

DELETE_SQL = """
DECLARE $user_id AS Utf8;
DECLARE $name AS Utf8;
DELETE FROM items WHERE user_id = $user_id AND name = $name;
"""

SEARCH_SQL = """
DECLARE $user_id AS Utf8;
DECLARE $query AS Utf8;
SELECT name FROM items WHERE user_id = $user_id AND name LIKE '%' || $query || '%';
"""

LIST_NAMES_SQL = """
DECLARE $user_id AS Utf8;
SELECT name FROM items WHERE user_id = $user_id;
"""

EXISTS_SQL = """
DECLARE $user_id AS Utf8;
DECLARE $name AS Utf8;
SELECT 1 AS exists_flag FROM items WHERE user_id = $user_id AND name = $name LIMIT 1;
"""


def _ensure_pool() -> ydb.QuerySessionPool | None:
    """Lazily initialize driver and pool on first call."""
    global _driver, _pool  # noqa: PLW0603

    if _pool is not None:
        return _pool

    if not YDB_ENDPOINT or not YDB_DATABASE:
        print("[db] YDB_ENDPOINT or YDB_DATABASE not set, skipping")
        return None

    print(f"[db] Initializing: {YDB_ENDPOINT} / {YDB_DATABASE}")
    try:
        credentials = ydb.iam.MetadataUrlCredentials()
        _driver = ydb.Driver(
            endpoint=YDB_ENDPOINT,
            database=YDB_DATABASE,
            credentials=credentials,
        )
        _driver.wait(fail_fast=True, timeout=5)
        _pool = ydb.QuerySessionPool(_driver)
        print("[db] YDB pool initialized")
        return _pool
    except Exception as e:
        print(f"[db] FAILED to init YDB: {e}")
        return None


def is_available() -> bool:
    """Check if YDB is configured and reachable."""
    return _ensure_pool() is not None


class YdbItemsRepository:
    """Реализация ItemsRepository на YDB."""

    def upsert_item(self, user_id: str, name: str, place: str) -> None:
        """Save or update an item in YDB."""
        pool = _ensure_pool()
        if pool is None:
            print(f"[db] upsert SKIPPED (no pool): {user_id} / {name}")
            return

        try:
            pool.execute_with_retries(
                UPSERT_SQL,
                {
                    "$user_id": ydb.TypedValue(user_id, ydb.PrimitiveType.Utf8),
                    "$name": ydb.TypedValue(name, ydb.PrimitiveType.Utf8),
                    "$place": ydb.TypedValue(place, ydb.PrimitiveType.Utf8),
                    "$updated_at": ydb.TypedValue(
                        datetime.datetime.now(datetime.UTC),
                        ydb.PrimitiveType.Timestamp,
                    ),
                },
            )
            print(f"[db] upsert OK: {user_id} / {name} = {place}")
        except Exception as e:
            print(f"[db] upsert FAILED: {user_id} / {name} — {e}")

    def load_items(self, user_id: str) -> dict[str, str]:
        """Load all items for a user from YDB."""
        pool = _ensure_pool()
        if pool is None:
            print(f"[db] load SKIPPED (no pool): {user_id}")
            return {}

        try:
            result_sets = pool.execute_with_retries(
                SELECT_ALL_SQL,
                {"$user_id": ydb.TypedValue(user_id, ydb.PrimitiveType.Utf8)},
            )
            items: dict[str, str] = {}
            for row in result_sets[0].rows:
                items[row.name] = row.place
            print(f"[db] load OK: {user_id}, count={len(items)}")
            return items
        except Exception as e:
            print(f"[db] load FAILED: {user_id} — {e}")
            return {}

    def delete_item(self, user_id: str, name: str) -> None:
        """Delete a single item from YDB."""
        pool = _ensure_pool()
        if pool is None:
            print(f"[db] delete SKIPPED (no pool): {user_id} / {name}")
            return

        try:
            pool.execute_with_retries(
                DELETE_SQL,
                {
                    "$user_id": ydb.TypedValue(user_id, ydb.PrimitiveType.Utf8),
                    "$name": ydb.TypedValue(name, ydb.PrimitiveType.Utf8),
                },
            )
            print(f"[db] delete OK: {user_id} / {name}")
        except Exception as e:
            print(f"[db] delete FAILED: {user_id} / {name} — {e}")

    def search_items(self, user_id: str, query: str) -> list[str]:
        """Find item names matching a substring (case-insensitive via YDB LIKE)."""
        pool = _ensure_pool()
        if pool is None:
            print(f"[db] search SKIPPED (no pool): {user_id} / {query}")
            return []

        try:
            result_sets = pool.execute_with_retries(
                SEARCH_SQL,
                {
                    "$user_id": ydb.TypedValue(user_id, ydb.PrimitiveType.Utf8),
                    "$query": ydb.TypedValue(query, ydb.PrimitiveType.Utf8),
                },
            )
            names = [row.name for row in result_sets[0].rows]
            print(f"[db] search OK: {user_id} / {query}, count={len(names)}")
            return names
        except Exception as e:
            print(f"[db] search FAILED: {user_id} / {query} — {e}")
            return []

    def list_names(self, user_id: str) -> list[str]:
        """Return only item names for a user."""
        pool = _ensure_pool()
        if pool is None:
            print(f"[db] list_names SKIPPED (no pool): {user_id}")
            return []

        try:
            result_sets = pool.execute_with_retries(
                LIST_NAMES_SQL,
                {"$user_id": ydb.TypedValue(user_id, ydb.PrimitiveType.Utf8)},
            )
            names = [row.name for row in result_sets[0].rows]
            print(f"[db] list_names OK: {user_id}, count={len(names)}")
            return names
        except Exception as e:
            print(f"[db] list_names FAILED: {user_id} — {e}")
            return []

    def item_exists(self, user_id: str, name: str) -> bool:
        """Check if an exact item name exists for a user."""
        pool = _ensure_pool()
        if pool is None:
            print(f"[db] exists SKIPPED (no pool): {user_id} / {name}")
            return False

        try:
            result_sets = pool.execute_with_retries(
                EXISTS_SQL,
                {
                    "$user_id": ydb.TypedValue(user_id, ydb.PrimitiveType.Utf8),
                    "$name": ydb.TypedValue(name, ydb.PrimitiveType.Utf8),
                },
            )
            exists = len(result_sets[0].rows) > 0
            print(f"[db] exists OK: {user_id} / {name} = {exists}")
            return exists
        except Exception as e:
            print(f"[db] exists FAILED: {user_id} / {name} — {e}")
            return False
