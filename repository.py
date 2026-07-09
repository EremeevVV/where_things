from __future__ import annotations

from typing import Protocol


class ItemsRepository(Protocol):
    """Интерфейс хранилища вещей пользователя."""

    def upsert_item(self, user_id: str, name: str, place: str) -> None: ...
    def load_items(self, user_id: str) -> dict[str, str]: ...
    def delete_item(self, user_id: str, name: str) -> None: ...
