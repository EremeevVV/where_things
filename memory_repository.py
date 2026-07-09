from __future__ import annotations


class InMemoryItemsRepository:
    """In-memory fake для тестов."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, str]] = {}

    def upsert_item(self, user_id: str, name: str, place: str) -> None:
        if user_id not in self._store:
            self._store[user_id] = {}
        self._store[user_id][name] = place

    def load_items(self, user_id: str) -> dict[str, str]:
        return dict(self._store.get(user_id, {}))

    def delete_item(self, user_id: str, name: str) -> None:
        if user_id in self._store:
            self._store[user_id].pop(name, None)
