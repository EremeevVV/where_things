from __future__ import annotations

import json
import re
from typing import Any


def parse_intent(command: str) -> tuple[str, dict[str, str]]:
    """Parse command text into (intent, slots).

    Intents: SAVE, FIND, LIST, DELETE, UNKNOWN
    """
    c = command.strip().lower()

    # LIST
    if re.match(r"^(что\s+ты\s+помнишь|что\s+запомнено|список|все\s+вещи)", c):
        return "LIST", {}

    # SAVE: "запомни что X лежит Y" / "запомни X лежит Y"
    m = re.match(r"^запомни,?\s*что\s+(.+?)\s+лежит\s+(.+)$", c)
    if m:
        return "SAVE", {"thing": m.group(1).strip(), "place": m.group(2).strip()}

    m = re.match(r"^запомни\s+(.+?)\s+лежит\s+(.+)$", c)
    if m:
        return "SAVE", {"thing": m.group(1).strip(), "place": m.group(2).strip()}

    # SAVE incomplete: "запомни что X" / "запомни X" (no place)
    m = re.match(r"^запомни,?\s*что\s+(.+)$", c)
    if m:
        return "SAVE", {"thing": m.group(1).strip(), "place": ""}

    m = re.match(r"^запомни\s+(.+)$", c)
    if m:
        return "SAVE", {"thing": m.group(1).strip(), "place": ""}

    # FIND: "где лежит X" / "где X"
    m = re.match(r"^где\s+лежит\s+(.+)$", c)
    if m:
        return "FIND", {"thing": m.group(1).strip()}

    m = re.match(r"^где\s+(.+)$", c)
    if m:
        return "FIND", {"thing": m.group(1).strip()}

    # DELETE: "забудь про X" / "забудь X"
    m = re.match(r"^забудь\s+про\s+(.+)$", c)
    if m:
        return "DELETE", {"thing": m.group(1).strip()}

    m = re.match(r"^забудь\s+(.+)$", c)
    if m:
        return "DELETE", {"thing": m.group(1).strip()}

    return "UNKNOWN", {}


def get_items(event: dict[str, Any]) -> dict[str, str]:
    """Extract items dict from session_state."""
    state: dict[str, Any] = event.get("state", {}).get("session", {})
    return dict(state.get("items", {}))


def handle_launch(event: dict[str, Any]) -> dict[str, Any]:
    text = (
        "Привет! Я запоминаю, где лежат вещи. "
        "Скажите: «запомни, что паспорт лежит в ящике», "
        "а потом: «где лежит паспорт?»"
    )
    return {
        "version": event.get("version", "1.0"),
        "session": event.get("session", {}),
        "response": {"text": text, "tts": text, "end_session": False},
    }


def handle_save(event: dict[str, Any], thing: str, place: str) -> dict[str, Any]:
    version = event.get("version", "1.0")
    session = event.get("session", {})
    items = get_items(event)

    if not place:
        text = f"Где лежит {thing}? Скажите место."
        return {
            "version": version,
            "session": session,
            "session_state": {"items": items},
            "response": {"text": text, "tts": text, "end_session": False},
        }

    items[thing] = place
    text = f"Запомнила: {thing} — {place}."
    return {
        "version": version,
        "session": session,
        "session_state": {"items": items},
        "response": {"text": text, "tts": text, "end_session": False},
    }


def handle_find(event: dict[str, Any], thing: str) -> dict[str, Any]:
    version = event.get("version", "1.0")
    session = event.get("session", {})
    items = get_items(event)

    place = items.get(thing)
    if place:
        text = f"{thing.capitalize()} — {place}."
    else:
        text = f"Я не знаю, где лежит {thing}. Perhaps, запомните?"

    return {
        "version": version,
        "session": session,
        "session_state": {"items": items},
        "response": {"text": text, "tts": text, "end_session": False},
    }


def handle_list(event: dict[str, Any]) -> dict[str, Any]:
    version = event.get("version", "1.0")
    session = event.get("session", {})
    items = get_items(event)

    if not items:
        text = "Я пока ничего не помню."
    else:
        lines = [f"{name} — {place}" for name, place in items.items()]
        text = "Запомнено:\n" + "\n".join(lines)

    return {
        "version": version,
        "session": session,
        "session_state": {"items": items},
        "response": {"text": text, "tts": text, "end_session": False},
    }


def handle_delete(event: dict[str, Any], thing: str) -> dict[str, Any]:
    version = event.get("version", "1.0")
    session = event.get("session", {})
    items = get_items(event)

    if thing in items:
        del items[thing]
        text = f"Забыла про {thing}."
    else:
        text = f"У меня нет воспоминаний про {thing}."

    return {
        "version": version,
        "session": session,
        "session_state": {"items": items},
        "response": {"text": text, "tts": text, "end_session": False},
    }


def handle_unknown(event: dict[str, Any]) -> dict[str, Any]:
    version = event.get("version", "1.0")
    session = event.get("session", {})
    command = event.get("request", {}).get("command", "")
    text = f"Не поняла: «{command}». Скажите «запомни» или «где лежит»."
    return {
        "version": version,
        "session": session,
        "response": {"text": text, "tts": text, "end_session": False},
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Yandex Cloud Functions entry point."""
    session = event.get("session", {})
    request = event.get("request", {})
    command = request.get("command", "").strip()

    if session.get("new", False) or not command:
        return handle_launch(event)

    intent, slots = parse_intent(command)

    if intent == "SAVE":
        return handle_save(event, slots["thing"], slots["place"])
    elif intent == "FIND":
        return handle_find(event, slots["thing"])
    elif intent == "LIST":
        return handle_list(event)
    elif intent == "DELETE":
        return handle_delete(event, slots["thing"])
    else:
        return handle_unknown(event)


if __name__ == "__main__":
    with open("test_data/launch.json") as f:
        test_event = json.loads(f.read())
    result = handler(test_event, None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
