from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import db


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
          session_data — обновлённые данные сессии (dialog_state и т.д.)
          response_text — текст ответа пользователю
        """


def build_response(
    event: dict[str, Any],
    session_data: dict[str, Any],
    text: str,
    next_state: str = "IDLE",
) -> dict[str, Any]:
    """Собрать ответ для Yandex Dialogs.

    Items хранятся в YDB, в session_state — только состояние диалога.
    """
    version = event.get("version", "1.0")
    session = event.get("session", {})

    # В session_state — только данные диалога (без items)
    if next_state == "IDLE":
        state_to_return: dict[str, Any] = {}
    else:
        state_to_return = {
            "dialog_state": next_state,
            "pending_thing": session_data.get("pending_thing", ""),
            "state_visits": session_data.get("state_visits", 0),
        }

    return {
        "version": version,
        "session": session,
        "session_state": state_to_return,
        "response": {"text": text, "tts": text, "end_session": False},
    }


_NO_AUTH_TEXT = (
    "Для работы с памятью нужно авторизоваться через Яндекс ID. "
    "Откройте навык на колонке или в приложении с авторизацией."
)


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
        user_id: str = session_data.get("user_id", "")

        if not user_id:
            return "IDLE", session_data, _NO_AUTH_TEXT

        if intent == "SAVE":
            thing = slots.get("thing", "")
            place = slots.get("place", "")

            if place:
                db.upsert_item(user_id, thing, place)
                text = f"Запомнила: {thing} — {place}."
                return "IDLE", session_data, text
            else:
                # Неполное сохранение — переход в AwaitingPlaceState
                session_data["dialog_state"] = "AWAITING_PLACE"
                session_data["pending_thing"] = thing
                session_data["state_visits"] = 1
                text = f"Где лежит {thing}? Скажите место."
                return "AWAITING_PLACE", session_data, text

        if intent == "FIND":
            thing = slots.get("thing", "")
            items = db.load_items(user_id)
            found_place: str | None = items.get(thing)
            if found_place:
                text = f"{thing.capitalize()} — {found_place}."
            else:
                text = f"Я не знаю, где лежит {thing}."
            return "IDLE", session_data, text

        if intent == "LIST":
            items = db.load_items(user_id)
            if not items:
                text = "Я пока ничего не помню."
            else:
                lines = [f"{name} — {place}" for name, place in items.items()]
                text = "Запомнено:\n" + "\n".join(lines)
            return "IDLE", session_data, text

        if intent == "DELETE":
            thing = slots.get("thing", "")
            items = db.load_items(user_id)
            if thing in items:
                db.delete_item(user_id, thing)
                text = f"Забыла про {thing}."
            else:
                text = f"У меня нет воспоминаний про {thing}."
            return "IDLE", session_data, text

        # UNKNOWN — действие по умолчанию
        text = f"Не поняла: «{command}». Скажите «запомни» или «где лежит»."
        return "IDLE", session_data, text


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
        state_visits = session_data.get("state_visits", 1)
        user_id: str = session_data.get("user_id", "")

        if not user_id:
            return "IDLE", session_data, _NO_AUTH_TEXT

        # Если пользователь начал новое сохранение с полным набором слотов
        if intent == "SAVE" and slots.get("place"):
            thing = slots["thing"]
            place = slots["place"]
            db.upsert_item(user_id, thing, place)
            text = f"Запомнила: {thing} — {place}."
            return "IDLE", session_data, text

        # Если пользователь начал новое неполное сохранение
        if intent == "SAVE" and not slots.get("place"):
            new_thing = slots.get("thing", "")
            session_data["dialog_state"] = "AWAITING_PLACE"
            session_data["pending_thing"] = new_thing
            session_data["state_visits"] = 1
            text = f"Где лежит {new_thing}? Скажите место."
            return "AWAITING_PLACE", session_data, text

        # Если пришла явная команда, прерывающая диалог
        if intent in self._INTERRUPTING_INTENTS:
            idle = IdleState()
            next_state, updated_data, text = idle.handle(
                event, session_data, intent, slots
            )
            return next_state, updated_data, text

        # Текст не распознан как команда — по умолчанию считаем ответом
        # на вопрос "где лежит?". Если совсем короткий (менее 2 символов) —
        # переспросить с подсказкой.
        if pending_thing and len(command) >= 2:
            db.upsert_item(user_id, pending_thing, command)
            text = f"Запомнила: {pending_thing} — {command}."
            return "IDLE", session_data, text

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
        return "IDLE", session_data, "Не поняла. Начните заново."


STATE_REGISTRY: dict[str, type[DialogState]] = {
    "IDLE": IdleState,
    "AWAITING_PLACE": AwaitingPlaceState,
}
