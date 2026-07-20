from __future__ import annotations

type ItemRecord = tuple[str, str]
type ItemsMap = dict[str, ItemRecord]


class InMemoryItemsRepository:
    """In-memory fake для тестов."""

    def __init__(self) -> None:
        """Initialize empty store."""
        self._store: dict[str, ItemsMap] = {}

    def upsert_item(self, user_id: str, name: str, location: str, verb: str) -> None:
        """Insert or update an item."""
        if user_id not in self._store:
            self._store[user_id] = {}
        self._store[user_id][name] = (verb, location)

    def load_items(self, user_id: str) -> ItemsMap:
        """Load all items for a user. Returns {name: (verb, location)}."""
        return dict(self._store.get(user_id, {}))

    def delete_item(self, user_id: str, name: str) -> None:
        """Delete an item by name."""
        user_items = self._store.get(user_id)
        if user_items is not None:
            user_items.pop(name, None)

    def search_items(self, user_id: str, query: str) -> list[str]:
        """Find item names matching exactly (case-insensitive)."""
        stored_items = self._store.get(user_id, {})
        lower_query = query.lower()
        return [name for name in stored_items if name.lower() == lower_query]

    def list_names(self, user_id: str) -> list[str]:
        """List all item names."""
        return list(self._store.get(user_id, {}).keys())

    def item_exists(self, user_id: str, name: str) -> bool:
        """Check if an item exists."""
        return name in self._store.get(user_id, {})
