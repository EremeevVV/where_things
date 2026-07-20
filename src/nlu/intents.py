from __future__ import annotations

from dataclasses import dataclass

from aliceio.types import Message

from src.nlu.slots import get_intent, get_slot
from src.nlu.thing.normalize import normalize_thing

INTENT_SAVE = "save"
INTENT_FIND = "find"
INTENT_DELETE = "delete"


@dataclass
class SaveIntent:
    """Parsed save intent with slot values."""

    place: str
    display_name: str
    canonical_key: str
    preposition: str = ""
    verb: str = "лежит"

    @property
    def location(self) -> str:
        """Compose location string from preposition and place."""
        if self.preposition:
            return f"{self.preposition} {self.place}".strip()
        return self.place

    @classmethod
    def from_message(cls, message: Message) -> SaveIntent | None:
        """Parse save intent from message, or None if not present."""
        if get_intent(message, INTENT_SAVE) is None:
            return None
        raw = get_slot(message, INTENT_SAVE, "thing")
        if not raw:
            return None
        normalized = normalize_thing(raw)
        return cls(
            place=get_slot(message, INTENT_SAVE, "place"),
            display_name=normalized.display_name,
            canonical_key=normalized.canonical_key,
            preposition=get_slot(message, INTENT_SAVE, "preposition"),
            verb=get_slot(message, INTENT_SAVE, "loc_verb") or "лежит",
        )


@dataclass
class FindIntent:
    """Parsed find intent with slot values."""

    display_name: str
    canonical_key: str

    @classmethod
    def from_message(cls, message: Message) -> FindIntent | None:
        """Parse find intent from message, or None if not present."""
        if get_intent(message, INTENT_FIND) is None:
            return None
        raw = get_slot(message, INTENT_FIND, "thing")
        if not raw:
            return None
        normalized = normalize_thing(raw)
        return cls(
            display_name=normalized.display_name,
            canonical_key=normalized.canonical_key,
        )


@dataclass
class DeleteIntent:
    """Parsed delete intent with slot values."""

    display_name: str
    canonical_key: str

    @classmethod
    def from_message(cls, message: Message) -> DeleteIntent | None:
        """Parse delete intent from message, or None if not present."""
        if get_intent(message, INTENT_DELETE) is None:
            return None
        raw = get_slot(message, INTENT_DELETE, "thing")
        if not raw:
            return None
        normalized = normalize_thing(raw)
        return cls(
            display_name=normalized.display_name,
            canonical_key=normalized.canonical_key,
        )
