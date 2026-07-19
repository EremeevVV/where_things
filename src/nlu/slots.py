from __future__ import annotations

from typing import Any

from aliceio.types import Message


def get_intent(message: Message, intent_name: str) -> dict[str, Any] | None:
    """Get raw intent data from message NLU intents."""
    intents = message.nlu.intents if message.nlu else {}
    return intents.get(intent_name)


def get_slot(message: Message, intent_name: str, slot_name: str) -> str:
    """Extract slot value from message NLU intents.

    Returns empty string if message has no NLU, intent is missing,
    or slot is missing.
    """
    intents = message.nlu.intents if message.nlu else {}
    intent = intents.get(intent_name, {})
    slots = intent.get("slots", {})
    slot = slots.get(slot_name, {})
    return str(slot.get("value", ""))
