from __future__ import annotations


class InMemoryItemsRepository:
    """In-memory fake для тестов."""

    def __init__(self) -> None:
        """Initialize empty store."""
        self._store: dict[str, dict[str, tuple[str, str]]] = {}

    def upsert_item(self, user_id: str, name: str, location: str, verb: str) -> None:
        """Insert or update an item."""
        if user_id not in self._store:
            self._store[user_id] = {}
        self._store[user_id][name] = (verb, location)

    def load_items(self, user_id: str) -> dict[str, tuple[str, str]]:
        """Load all items for a user. Returns {name: (verb, location)}."""
        return dict(self._store.get(user_id, {}))

    def delete_item(self, user_id: str, name: str) -> None:
        """Delete an item by name."""
        if user_id in self._store:
            self._store[user_id].pop(name, None)

    def search_items(self, user_id: str, query: str) -> list[str]:
        """Find item names matching exactly (case-insensitive)."""
        items = self._store.get(user_id, {})
        q = query.lower()
        return [name for name in items if name.lower() == q]

    def list_names(self, user_id: str) -> list[str]:
        """List all item names."""
        return list(self._store.get(user_id, {}).keys())

    def item_exists(self, user_id: str, name: str) -> bool:
        """Check if an item exists."""
        return name in self._store.get(user_id, {})
