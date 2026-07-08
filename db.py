from __future__ import annotations

import os
import time
from typing import Any

import ydb
import ydb.iam

# ── YDB driver + session pool (module level — reused across warm invocations) ──

# Глобальные переменные для переиспользования соединения между вызовами
# (warm start). Критически важно для скорости.

_driver: ydb.Driver | None = None
_pool: ydb.SessionPool | None = None

YDB_ENDPOINT = os.getenv("YDB_ENDPOINT", "")
YDB_DATABASE = os.getenv("YDB_DATABASE", "")



def _ensure_driver() -> ydb.SessionPool | None:
    """Lazily initialize driver and pool on first call."""
    global _driver, _pool

    # Если драйвер и пул уже инициализированы и живы, возвращаем пул
    if _pool is not None and not _pool.is_shutdown:
        return _pool

    if not os.getenv('YDB_ENDPOINT') or not os.getenv('YDB_DATABASE'):
        print("[db] YDB_ENDPOINT or YDB_DATABASE not set, skipping")
        return None

    try:
        # 1. Создаем драйвер с ЯВНЫМИ учетными данными
        # Для Yandex Functions рекомендуется MetadataUrlCredentials
        # Они автоматически получают токен от IAM метаданных
        credentials = ydb.iam.MetadataUrlCredentials()

        _driver = ydb.Driver(
            endpoint=os.getenv('YDB_ENDPOINT'),
            database=os.getenv('YDB_DATABASE'),
            credentials=credentials
        )

        # 2. Ждем подключения.
        # Таймаут может быть маловат для первого соединения.
        # Но для навыка Алисы мы ограничены 4.5с общими.
        try:
            _driver.wait(fail_fast=True, timeout=3)
        except ydb.issues.TimeoutError:
            print("[db] Driver wait timeout")
            return None

        # 3. Создаем пул сессий.
        # SessionPool тоже нужно создавать на уровне драйвера.
        _pool = ydb.SessionPool(_driver)
        print("[db] YDB driver and pool initialized successfully")
        return _pool

    except Exception as e:
        print(f"[db] FAILED to initialize YDB driver: {e}")
        # Для отладки можно добавить traceback.format_exc()
        return None


def is_available() -> bool:
    """Check if YDB is configured and reachable."""
    return _ensure_driver() is not None


# ── CRUD ──────────────────────────────────────────────────────────────────────

_UPSERT_SQL = """
DECLARE $user_id AS Utf8;
DECLARE $name AS Utf8;
DECLARE $place AS Utf8;
DECLARE $updated_at AS Timestamp;
UPSERT INTO items (user_id, name, place, updated_at)
VALUES ($user_id, $name, $place, $updated_at);
"""

_SELECT_ALL_SQL = """
DECLARE $user_id AS Utf8;
SELECT name, place FROM items WHERE user_id = $user_id;
"""

_DELETE_SQL = """
DECLARE $user_id AS Utf8;
DECLARE $name AS Utf8;
DELETE FROM items WHERE user_id = $user_id AND name = $name;
"""

_SETTINGS = ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)


def upsert_item(user_id: str, name: str, place: str) -> None:
    """Save or update an item in YDB."""
    pool = _ensure_driver()
    if pool is None:
        print(f"[db] upsert SKIPPED (no pool): {user_id} / {name}")
        return

    def _callee(session: Any) -> None:
        session.transaction().execute(
            _UPSERT_SQL,
            {
                "user_id": user_id.encode(),
                "name": name.encode(),
                "place": place.encode(),
                "updated_at": int(time.time() * 1_000_000),
            },
            commit_tx=True,
            settings=_SETTINGS,
        )

    try:
        pool.retry_operation_sync(_callee)
        print(f"[db] upsert OK: {user_id} / {name} = {place}")
    except Exception as e:
        print(f"[db] upsert FAILED: {user_id} / {name} — {e}")


def load_items(user_id: str) -> dict[str, str]:
    """Load all items for a user from YDB."""
    pool = _ensure_driver()
    if pool is None:
        print(f"[db] load SKIPPED (no pool): {user_id}")
        return {}

    result: dict[str, str] = {}

    def _callee(session: Any) -> None:
        nonlocal result
        res = session.transaction().execute(
            _SELECT_ALL_SQL,
            {"user_id": user_id.encode()},
            commit_tx=True,
            settings=_SETTINGS,
        )
        for row in res[0].rows:
            result[row.name.decode()] = row.place.decode()

    try:
        pool.retry_operation_sync(_callee)
        print(f"[db] load OK: {user_id}, count={len(result)}")
    except Exception as e:
        print(f"[db] load FAILED: {user_id} — {e}")
    return result


def delete_item(user_id: str, name: str) -> None:
    """Delete a single item from YDB."""
    pool = _ensure_driver()
    if pool is None:
        print(f"[db] delete SKIPPED (no pool): {user_id} / {name}")
        return

    def _callee(session: Any) -> None:
        session.transaction().execute(
            _DELETE_SQL,
            {
                "user_id": user_id.encode(),
                "name": name.encode(),
            },
            commit_tx=True,
            settings=_SETTINGS,
        )

    try:
        pool.retry_operation_sync(_callee)
        print(f"[db] delete OK: {user_id} / {name}")
    except Exception as e:
        print(f"[db] delete FAILED: {user_id} / {name} — {e}")
