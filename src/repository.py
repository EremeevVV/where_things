from __future__ import annotations

from typing import Protocol


class ItemsRepository(Protocol):
    """Интерфейс хранилища вещей пользователя."""

    def upsert_item(self, user_id: str, name: str, location: str, verb: str) -> None:
        """Insert or update an item."""
        ...

    def load_items(self, user_id: str) -> dict[str, tuple[str, str]]:
        """Load all items for a user. Returns {name: (verb, location)}."""
        ...

    def delete_item(self, user_id: str, name: str) -> None:
        """Delete an item by name."""
        ...

    def search_items(self, user_id: str, query: str) -> list[str]:
        """Search items by exact name (case-insensitive)."""
        ...

    def list_names(self, user_id: str) -> list[str]:
        """List all item names."""
        ...

    def item_exists(self, user_id: str, name: str) -> bool:
        """Check if an item exists."""
        ...
