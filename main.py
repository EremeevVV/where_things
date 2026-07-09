from __future__ import annotations

import logging
from typing import Any

from nlu import parse_intent
from states import STATE_REGISTRY, StateName, build_response
from ydb_repository import YdbItemsRepository

logger = logging.getLogger(__name__)

_repo = YdbItemsRepository()


def _get_version(event: dict[str, Any]) -> str:
    """Получить версию из event (единая точка дефолта)."""
    return str(event.get("version", "1.0"))


def _fallback_response(event: dict[str, Any]) -> dict[str, Any]:
    """Минимальный валидный ответ при необработанной ошибке."""
    return {
        "version": _get_version(event),
        "session": event.get("session", {}),
        "response": {
            "text": "Извините, что-то пошло не так. Повторите, пожалуйста.",
            "tts": "Извините, что-то пошло не так. Повторите, пожалуйста.",
            "end_session": False,
        },
    }


def handle_launch(event: dict[str, Any]) -> dict[str, Any]:
    """Обработка запуска навыка (session.new == true)."""
    text = (
        "Привет! Я запоминаю, где лежат вещи. "
        "Скажите: «запомни, что паспорт лежит в ящике», "
        "а потом: «где лежит паспорт?»"
    )
    return {
        "version": _get_version(event),
        "session": event.get("session", {}),
        "response": {"text": text, "tts": text, "end_session": False},
    }


def _handle(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Основная логика обработки (без try/except)."""
    session = event.get("session", {})
    request = event.get("request", {})
    command = request.get("command", "").strip()

    # Запуск навыка или пустая команда — приветствие
    if session.get("new", False) or not command:
        return handle_launch(event)

    # Парсим намерение
    intent, slots = parse_intent(command)

    # Читаем данные сессии и user_id
    session_data: dict[str, Any] = dict(
        event.get("state", {}).get("session", {})
    )
    user_id: str = session.get("user", {}).get("user_id", "")
    session_data["user_id"] = user_id

    # Определяем текущее состояние
    state_name_str = session_data.get("dialog_state", StateName.IDLE.value)
    try:
        state_name = StateName(state_name_str)
    except ValueError:
        logger.warning("unknown state name: %s, falling back to IDLE", state_name_str)
        state_name = StateName.IDLE

    state_class = STATE_REGISTRY[state_name]
    state = state_class()

    logger.info(
        "intent=%s state=%s cmd_len=%d user=%s",
        intent.value,
        state_name.value,
        len(command),
        user_id[:8] if user_id else "",
    )

    # делаем копию session_data, чтобы состояния не мутировали оригинал
    next_state, updated_data, text = state.handle(
        event, dict(session_data), intent, slots, _repo
    )

    return build_response(event, updated_data, text, next_state)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Yandex Cloud Functions entry point.

    Оборачивает _handle в try/except для устойчивости к багам.
    """
    try:
        return _handle(event, context)
    except Exception:
        logger.exception("unhandled error in handler")
        return _fallback_response(event)
