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
DECLARE $location AS Utf8;
DECLARE $verb AS Utf8;
DECLARE $updated_at AS Timestamp;
UPSERT INTO items (user_id, name, location, verb, updated_at)
VALUES ($user_id, $name, $location, $verb, $updated_at);
"""

SELECT_ALL_SQL = """
DECLARE $user_id AS Utf8;
SELECT name, location, verb FROM items WHERE user_id = $user_id;
"""

DELETE_SQL = """
DECLARE $user_id AS Utf8;
DECLARE $name AS Utf8;
DELETE FROM items WHERE user_id = $user_id AND name = $name;
"""

SEARCH_SQL = """
DECLARE $user_id AS Utf8;
DECLARE $query AS Utf8;
SELECT name FROM items WHERE user_id = $user_id AND Unicode::ToLower(name) = Unicode::ToLower($query);
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
    except Exception as e:
        print(f"[db] FAILED to init YDB: {e}")
        return None
    else:
        print("[db] YDB pool initialized")
        return _pool


def is_available() -> bool:
    """Check if YDB is configured and reachable."""
    return _ensure_pool() is not None


class YdbItemsRepository:
    """Реализация ItemsRepository на YDB."""

    def upsert_item(self, user_id: str, name: str, location: str, verb: str) -> None:
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
                    "$location": ydb.TypedValue(location, ydb.PrimitiveType.Utf8),
                    "$verb": ydb.TypedValue(verb, ydb.PrimitiveType.Utf8),
                    "$updated_at": ydb.TypedValue(
                        datetime.datetime.now(datetime.UTC),
                        ydb.PrimitiveType.Timestamp,
                    ),
                },
            )
            print(f"[db] upsert OK: {user_id} / {name} = {verb} {location}")
        except Exception as e:
            print(f"[db] upsert FAILED: {user_id} / {name} — {e}")

    def load_items(self, user_id: str) -> dict[str, tuple[str, str]]:
        """Load all items for a user from YDB. Returns {name: (verb, location)}."""
        pool = _ensure_pool()
        if pool is None:
            print(f"[db] load SKIPPED (no pool): {user_id}")
            return {}

        try:
            result_sets = pool.execute_with_retries(
                SELECT_ALL_SQL,
                {"$user_id": ydb.TypedValue(user_id, ydb.PrimitiveType.Utf8)},
            )
            result_items: dict[str, tuple[str, str]] = {}
            for row in result_sets[0].rows:
                result_items[row.name] = (row.verb, row.location)
        except Exception as e:
            print(f"[db] load FAILED: {user_id} — {e}")
            return {}
        else:
            print(f"[db] load OK: {user_id}, count={len(result_items)}")
            return result_items

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
        """Find item names matching exactly (case-insensitive)."""
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
        except Exception as e:
            print(f"[db] search FAILED: {user_id} / {query} — {e}")
            return []
        else:
            print(f"[db] search OK: {user_id} / {query}, count={len(names)}")
            return names

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
        except Exception as e:
            print(f"[db] list_names FAILED: {user_id} — {e}")
            return []
        else:
            print(f"[db] list_names OK: {user_id}, count={len(names)}")
            return names

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
        except Exception as e:
            print(f"[db] exists FAILED: {user_id} / {name} — {e}")
            return False
        else:
            print(f"[db] exists OK: {user_id} / {name} = {exists}")
            return exists
