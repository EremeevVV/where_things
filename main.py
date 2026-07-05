from __future__ import annotations

import json
import re
from typing import Any

from states import STATE_REGISTRY, build_response


def parse_intent(command: str) -> tuple[str, dict[str, str]]:
    """Parse command text into (intent, slots).

    Intents: SAVE, FIND, LIST, DELETE, UNKNOWN
    """
    c = command.strip().lower()

    # LIST
    if re.match(r"^(что\s+ты\s+помнишь|что\s+запомнено|список|все\s+вещи)", c):
        return "LIST", {}

    # SAVE: "запомни что X лежит Y" / "запомни X лежит Y"
    m = re.match(r"^запомни,?\s*что\s+(.+?)\s+леж[иа]т\s+(.+)$", c)
    if m:
        return "SAVE", {"thing": m.group(1).strip(), "place": m.group(2).strip()}

    m = re.match(r"^запомни\s+(.+?)\s+леж[иа]т\s+(.+)$", c)
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
    m = re.match(r"^где\s+леж[иа]т\s+(.+)$", c)
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


def handle_launch(event: dict[str, Any]) -> dict[str, Any]:
    """Обработка запуска навыка (session.new == true)."""
    text = (
        "Привет! Я запоминаю, где лежат вещи. "
        "Скажите: «запомни, что паспорт лежит в ящике», "
        "а потом: «где лежит паспорт?»"
    )
    version = event.get("version", "1.0")
    session = event.get("session", {})
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

    # Запуск навыка или пустая команда — приветствие
    if session.get("new", False) or not command:
        return handle_launch(event)

    # Парсим намерение
    intent, slots = parse_intent(command)

    # Читаем данные сессии
    session_data: dict[str, Any] = dict(
        event.get("state", {}).get("session", {})
    )

    # Определяем текущее состояние
    state_name = session_data.get("dialog_state", "IDLE")
    state_class = STATE_REGISTRY.get(state_name, STATE_REGISTRY["IDLE"])
    state = state_class()

    # делаем копию session_data, чтобы состояния не мутировали оригинал
    next_state, updated_data, text = state.handle(
        event, dict(session_data), intent, slots
    )

    return build_response(event, updated_data, text, next_state)


if __name__ == "__main__":
    with open("test_data/launch.json") as f:
        test_event = json.loads(f.read())
    result = handler(test_event, None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
