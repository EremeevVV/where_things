from __future__ import annotations

from src.repository import ItemRecord


class InMemoryItemsRepository:
    """In-memory fake для тестов."""

    def __init__(self) -> None:
        """Initialize empty store."""
        self._store: dict[str, dict[str, ItemRecord]] = {}

    def upsert_item(
        self,
        user_id: str,
        canonical_key: str,
        display_name: str,
        location: str,
        verb: str,
    ) -> None:
        """Insert or update an item."""
        if user_id not in self._store:
            self._store[user_id] = {}
        self._store[user_id][canonical_key] = ItemRecord(
            display_name=display_name,
            location=location,
            verb=verb,
        )

    def find_by_canonical_key(
        self,
        user_id: str,
        canonical_key: str,
    ) -> ItemRecord | None:
        """Find an item by its canonical key."""
        return self._store.get(user_id, {}).get(canonical_key)

    def delete_item(self, user_id: str, canonical_key: str) -> None:
        """Delete an item by canonical key."""
        user_items = self._store.get(user_id)
        if user_items is not None:
            user_items.pop(canonical_key, None)

    def list_display_names(self, user_id: str) -> list[str]:
        """List all display names for a user."""
        return [r.display_name for r in self._store.get(user_id, {}).values()]
