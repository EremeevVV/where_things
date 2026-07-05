from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DialogState(ABC):
    """Базовый интерфейс состояния диалога."""

    @abstractmethod
    def handle(
        self,
        event: dict[str, Any],
        session_data: dict[str, Any],
        intent: str,
        slots: dict[str, str],
    ) -> tuple[str, dict[str, Any], str]:
        """Обработать входящее событие.

        Возвращает:
          next_state_name — имя следующего состояния ("IDLE" или текущее)
          session_data — обновлённые данные сессии
          response_text — текст ответа пользователю
        """


def build_response(
    event: dict[str, Any],
    session_data: dict[str, Any],
    text: str,
    next_state: str = "IDLE",
) -> dict[str, Any]:
    """Собрать ответ для Yandex Dialogs.

    Формирует session_state и response в правильном формате.
    """
    version = event.get("version", "1.0")
    session = event.get("session", {})

    # Если состояние IDLE — убираем dialog_state из ответа (экономим место)
    if next_state == "IDLE":
        state_to_return: dict[str, Any] = {
            "items": session_data.get("items", {}),
        }
    else:
        state_to_return = {
            "dialog_state": next_state,
            "pending_thing": session_data.get("pending_thing", ""),
            "state_visits": session_data.get("state_visits", 0),
            "items": session_data.get("items", {}),
        }

    return {
        "version": version,
        "session": session,
        "session_state": state_to_return,
        "response": {"text": text, "tts": text, "end_session": False},
    }


class IdleState(DialogState):
    """Обычный режим: парсинг команд и выполнение действий."""

    def handle(
        self,
        event: dict[str, Any],
        session_data: dict[str, Any],
        intent: str,
        slots: dict[str, str],
    ) -> tuple[str, dict[str, Any], str]:
        command = event.get("request", {}).get("command", "").strip()
        items = dict(session_data.get("items", {}))

        if intent == "SAVE":
            thing = slots.get("thing", "")
            place = slots.get("place", "")

            if place:
                items[thing] = place
                text = f"Запомнила: {thing} — {place}."
                return (
                    "IDLE",
                    {"items": items},
                    text,
                )
            else:
                # Неполное сохранение — переход в AwaitingPlaceState
                session_data["dialog_state"] = "AWAITING_PLACE"
                session_data["pending_thing"] = thing
                session_data["state_visits"] = 1
                text = f"Где лежит {thing}? Скажите место."
                return (
                    "AWAITING_PLACE",
                    session_data,
                    text,
                )

        if intent == "FIND":
            thing = slots.get("thing", "")
            found_place: str | None = items.get(thing)
            if found_place:
                text = f"{thing.capitalize()} — {found_place}."
            else:
                text = f"Я не знаю, где лежит {thing}."
            return "IDLE", {"items": items}, text

        if intent == "LIST":
            if not items:
                text = "Я пока ничего не помню."
            else:
                lines = [f"{name} — {place}" for name, place in items.items()]
                text = "Запомнено:\n" + "\n".join(lines)
            return "IDLE", {"items": items}, text

        if intent == "DELETE":
            thing = slots.get("thing", "")
            if thing in items:
                del items[thing]
                text = f"Забыла про {thing}."
            else:
                text = f"У меня нет воспоминаний про {thing}."
            return "IDLE", {"items": items}, text

        # UNKNOWN — действие по умолчанию
        text = f"Не поняла: «{command}». Скажите «запомни» или «где лежит»."
        return "IDLE", {"items": items}, text


class AwaitingPlaceState(DialogState):
    """Ждём место для неполного сохранения.

    Обработка:
    - Если пользователь назвал явную команду — прерываем, выполняем её.
    - Если текст похож на ответ — сохраняем как место.
    - Если не распознано — переспрос с эскалацией подсказок.
    """

    # Команды, которые прерывают текущий диалог
    _INTERRUPTING_INTENTS = {"FIND", "LIST", "DELETE"}

    def handle(
        self,
        event: dict[str, Any],
        session_data: dict[str, Any],
        intent: str,
        slots: dict[str, str],
    ) -> tuple[str, dict[str, Any], str]:
        command = event.get("request", {}).get("command", "").strip()
        pending_thing = session_data.get("pending_thing", "")
        items = dict(session_data.get("items", {}))
        state_visits = session_data.get("state_visits", 1)

        # Если пользователь начал новое сохранение с полным набором слотов
        if intent == "SAVE" and slots.get("place"):
            thing = slots["thing"]
            place = slots["place"]
            items[thing] = place
            text = f"Запомнила: {thing} — {place}."
            return "IDLE", {"items": items}, text

        # Если пользователь начал новое неполное сохранение
        if intent == "SAVE" and not slots.get("place"):
            new_thing = slots.get("thing", "")
            session_data["dialog_state"] = "AWAITING_PLACE"
            session_data["pending_thing"] = new_thing
            session_data["state_visits"] = 1
            session_data["items"] = items
            text = f"Где лежит {new_thing}? Скажите место."
            return "AWAITING_PLACE", session_data, text

        # Если пришла явная команда, прерывающая диалог
        # Выполняем её через IdleState и возвращаемся в IDLE
        if intent in self._INTERRUPTING_INTENTS:
            idle = IdleState()
            next_state, updated_data, text = idle.handle(
                event, session_data, intent, slots
            )
            updated_data["items"] = items  # гарантируем актуальность items
            return next_state, updated_data, text

        # Текст не распознан как команда — по умолчанию считаем ответом
        # на вопрос "где лежит?". Если совсем короткий (менее 2 символов) —
        # переспросить с подсказкой.
        if pending_thing and len(command) >= 2:
            items[pending_thing] = command
            text = f"Запомнила: {pending_thing} — {command}."
            return "IDLE", {"items": items}, text

        # Пустой или слишком короткий ответ — переспросить
        if pending_thing:
            if state_visits < 2:
                text = "Скажите место."
            elif state_visits < 3:
                text = (
                    "Например: «в верхнем ящике стола» или «на полке у окна»."
                )
            else:
                text = (
                    f"Подскажите, где лежит {pending_thing}? "
                    "Любой ответ подойдёт."
                )
            session_data["state_visits"] = state_visits + 1
            return "AWAITING_PLACE", session_data, text

        # Нет pending_thing — нестандартная ситуация, возврат в IDLE
        return "IDLE", {"items": items}, "Не поняла. Начните заново."


STATE_REGISTRY: dict[str, type[DialogState]] = {
    "IDLE": IdleState,
    "AWAITING_PLACE": AwaitingPlaceState,
}
