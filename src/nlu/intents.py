from __future__ import annotations

from dataclasses import dataclass

from aliceio.types import Message

from src.nlu.slots import get_intent, get_slot


@dataclass
class SaveIntent:
    """Parsed save intent with slot values."""

    thing: str
    place: str
    preposition: str = ""
    verb: str = "лежит"

    @property
    def location(self) -> str:
        """Compose location string from preposition and place."""
        if self.preposition:
            return f"{self.preposition} {self.place}".strip()
        return self.place

    @property
    def is_complete(self) -> bool:
        """Check if intent has both thing and location."""
        return bool(self.thing and self.location)

    @classmethod
    def from_message(cls, message: Message) -> SaveIntent | None:
        """Parse save intent from message, or None if not present."""
        if get_intent(message, "save") is None:
            return None
        return cls(
            thing=get_slot(message, "save", "thing"),
            place=get_slot(message, "save", "place"),
            preposition=get_slot(message, "save", "preposition"),
            verb=get_slot(message, "save", "loc_verb") or "лежит",
        )


@dataclass
class FindIntent:
    """Parsed find intent with slot values."""

    thing: str

    @classmethod
    def from_message(cls, message: Message) -> FindIntent | None:
        """Parse find intent from message, or None if not present."""
        if get_intent(message, "find") is None:
            return None
        return cls(thing=get_slot(message, "find", "thing"))


@dataclass
class DeleteIntent:
    """Parsed delete intent with slot values."""

    thing: str

    @classmethod
    def from_message(cls, message: Message) -> DeleteIntent | None:
        """Parse delete intent from message, or None if not present."""
        if get_intent(message, "delete") is None:
            return None
        return cls(thing=get_slot(message, "delete", "thing"))
