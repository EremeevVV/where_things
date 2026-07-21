from __future__ import annotations

import datetime
import os

import ydb
import ydb.iam
from loguru import logger

from src.db.protocol import ItemRecord

# ── YDB driver + query pool (module level — reused across warm invocations) ──

_driver: ydb.Driver | None = None
_pool: ydb.QuerySessionPool | None = None

YDB_ENDPOINT = os.getenv("YDB_ENDPOINT", "")
YDB_DATABASE = os.getenv("YDB_DATABASE", "")

# ── SQL ───────────────────────────────────────────────────────────────────────

UPSERT_SQL = """
DECLARE $user_id AS Utf8;
DECLARE $canonical_key AS Utf8;
DECLARE $display_name AS Utf8;
DECLARE $location AS Utf8;
DECLARE $verb AS Utf8;
DECLARE $updated_at AS Timestamp;
UPSERT INTO items (user_id, canonical_key, display_name, location, verb, updated_at)
VALUES ($user_id, $canonical_key, $display_name, $location, $verb, $updated_at);
"""

DELETE_SQL = """
DECLARE $user_id AS Utf8;
DECLARE $canonical_key AS Utf8;
DELETE FROM items WHERE user_id = $user_id AND canonical_key = $canonical_key;
"""

FIND_BY_KEY_SQL = """
DECLARE $user_id AS Utf8;
DECLARE $canonical_key AS Utf8;
SELECT display_name, location, verb FROM items
WHERE user_id = $user_id AND canonical_key = $canonical_key
LIMIT 1;
"""

LIST_DISPLAY_NAMES_SQL = """
DECLARE $user_id AS Utf8;
SELECT display_name FROM items WHERE user_id = $user_id;
"""


def _ensure_pool() -> ydb.QuerySessionPool | None:
    """Lazily initialize driver and pool on first call."""
    global _driver, _pool  # noqa: PLW0603

    if _pool is not None:
        return _pool

    if not YDB_ENDPOINT or not YDB_DATABASE:
        logger.info("YDB_ENDPOINT or YDB_DATABASE not set, skipping")
        return None

    logger.info("Initializing: endpoint={ep} / db={db}", ep=YDB_ENDPOINT, db=YDB_DATABASE)
    try:
        credentials = ydb.iam.MetadataUrlCredentials()
        _driver = ydb.Driver(
            endpoint=YDB_ENDPOINT,
            database=YDB_DATABASE,
            credentials=credentials,
        )
        _driver.wait(fail_fast=True, timeout=5)
        _pool = ydb.QuerySessionPool(_driver)
    except Exception:
        logger.opt(exception=True).error("FAILED to init YDB")
        return None
    else:
        logger.info("YDB pool initialized")
        return _pool


def is_available() -> bool:
    """Check if YDB is configured and reachable."""
    return _ensure_pool() is not None


class YdbItemsRepository:
    """Реализация ItemsRepository на YDB."""

    def upsert_item(
        self,
        user_id: str,
        canonical_key: str,
        display_name: str,
        location: str,
        verb: str,
    ) -> None:
        """Save or update an item in YDB."""
        pool = _ensure_pool()
        if pool is None:
            logger.info("upsert SKIPPED (no pool): uid={uid} / key={key}", uid=user_id[:8], key=canonical_key)
            return

        try:
            pool.execute_with_retries(
                UPSERT_SQL,
                {
                    "$user_id": ydb.TypedValue(user_id, ydb.PrimitiveType.Utf8),
                    "$canonical_key": ydb.TypedValue(canonical_key, ydb.PrimitiveType.Utf8),
                    "$display_name": ydb.TypedValue(display_name, ydb.PrimitiveType.Utf8),
                    "$location": ydb.TypedValue(location, ydb.PrimitiveType.Utf8),
                    "$verb": ydb.TypedValue(verb, ydb.PrimitiveType.Utf8),
                    "$updated_at": ydb.TypedValue(
                        datetime.datetime.now(datetime.UTC),
                        ydb.PrimitiveType.Timestamp,
                    ),
                },
            )
            logger.info(
                "upsert OK: uid={uid} / key={key} [{name}] = {verb} {loc}",
                uid=user_id[:8],
                key=canonical_key,
                name=display_name,
                verb=verb,
                loc=location,
            )
        except Exception:
            logger.opt(exception=True).error("upsert FAILED: uid={uid} / key={key}", uid=user_id[:8], key=canonical_key)

    def find_by_canonical_key(
        self,
        user_id: str,
        canonical_key: str,
    ) -> ItemRecord | None:
        """Find an item by its canonical key."""
        pool = _ensure_pool()
        if pool is None:
            logger.info("find SKIPPED (no pool): uid={uid} / key={key}", uid=user_id[:8], key=canonical_key)
            return None

        try:
            result_sets = pool.execute_with_retries(
                FIND_BY_KEY_SQL,
                {
                    "$user_id": ydb.TypedValue(user_id, ydb.PrimitiveType.Utf8),
                    "$canonical_key": ydb.TypedValue(canonical_key, ydb.PrimitiveType.Utf8),
                },
            )
            rows = result_sets[0].rows
            if not rows:
                item = None
            else:
                row = rows[0]
                item = ItemRecord(
                    display_name=row.display_name,
                    location=row.location,
                    verb=row.verb,
                )
        except Exception:
            logger.opt(exception=True).error("find FAILED: uid={uid} / key={key}", uid=user_id[:8], key=canonical_key)
            return None
        else:
            found = "yes" if item else "no"
            logger.info("find OK: uid={uid} / key={key}, found={f}", uid=user_id[:8], key=canonical_key, f=found)
            return item

    def delete_item(self, user_id: str, canonical_key: str) -> None:
        """Delete a single item from YDB."""
        pool = _ensure_pool()
        if pool is None:
            logger.info("delete SKIPPED (no pool): uid={uid} / key={key}", uid=user_id[:8], key=canonical_key)
            return

        try:
            pool.execute_with_retries(
                DELETE_SQL,
                {
                    "$user_id": ydb.TypedValue(user_id, ydb.PrimitiveType.Utf8),
                    "$canonical_key": ydb.TypedValue(canonical_key, ydb.PrimitiveType.Utf8),
                },
            )
            logger.info("delete OK: uid={uid} / key={key}", uid=user_id[:8], key=canonical_key)
        except Exception:
            logger.opt(exception=True).error("delete FAILED: uid={uid} / key={key}", uid=user_id[:8], key=canonical_key)

    def list_display_names(self, user_id: str) -> list[str]:
        """Return all display names for a user."""
        pool = _ensure_pool()
        if pool is None:
            logger.info("list_names SKIPPED (no pool): uid={uid}", uid=user_id[:8])
            return []

        try:
            result_sets = pool.execute_with_retries(
                LIST_DISPLAY_NAMES_SQL,
                {"$user_id": ydb.TypedValue(user_id, ydb.PrimitiveType.Utf8)},
            )
            names = [row.display_name for row in result_sets[0].rows]
        except Exception:
            logger.opt(exception=True).error("list_names FAILED: uid={uid}", uid=user_id[:8])
            return []
        else:
            logger.info("list_names OK: uid={uid}, count={c}", uid=user_id[:8], c=len(names))
            return names
