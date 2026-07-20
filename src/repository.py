from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ItemRecord:
    """Canonical record for a stored item."""

    display_name: str
    location: str
    verb: str


class ItemsRepository(Protocol):
    """Интерфейс хранилища вещей пользователя."""

    def upsert_item(
        self,
        user_id: str,
        canonical_key: str,
        display_name: str,
        location: str,
        verb: str,
    ) -> None:
        """Insert or update an item."""
        ...

    def find_by_canonical_key(
        self,
        user_id: str,
        canonical_key: str,
    ) -> ItemRecord | None:
        """Find an item by its canonical key."""
        ...

    def delete_item(self, user_id: str, canonical_key: str) -> None:
        """Delete an item by canonical key."""
        ...

    def list_display_names(self, user_id: str) -> list[str]:
        """List all display names for a user."""
        ...
