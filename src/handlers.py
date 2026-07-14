from __future__ import annotations

import logging
from typing import Any

from aliceio import BaseMiddleware, Dispatcher, F, Router
from aliceio.fsm.context import FSMContext
from aliceio.fsm.state import State, StatesGroup
from aliceio.types import AliceResponse, Message, Response, Update

from src.repository import ItemsRepository

logger = logging.getLogger(__name__)

# ── FSM ───────────────────────────────────────────────────────────────────────


class SaveForm(StatesGroup):
    awaiting_confirmation = State()


# ── Router ────────────────────────────────────────────────────────────────────

router = Router(name="where_things")

# ── Middleware ─────────────────────────────────────────────────────────────────

_NO_AUTH_TEXT = (
    "Для работы с памятью нужно авторизоваться через Яндекс ID. "
    "Откройте навык на колонке или в приложении с авторизацией."
)


class AuthMiddleware(BaseMiddleware[Update]):
    """Блокирует неавторизованных пользователей."""

    async def __call__(
        self,
        handler: Any,
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        session = event.session
        if not session or not session.user:
            return AliceResponse(response=Response(text=_NO_AUTH_TEXT))
        return await handler(event, data)


# ── Setup ─────────────────────────────────────────────────────────────────────


def setup_handlers(dp: Dispatcher) -> None:
    dp.include_router(router)
    dp.update.outer_middleware(AuthMiddleware())


# ── Helpers ───────────────────────────────────────────────────────────────────


def _user_id(message: Message) -> str:
    return message.session.user.user_id if message.session.user else ""


def _slot_value(message: Message, intent_name: str, slot_name: str) -> str:
    """Extract slot value from Yandex Dialogs NLU intents."""
    intents = message.nlu.intents if message.nlu else {}
    intent = intents.get(intent_name, {})
    slots = intent.get("slots", {})
    slot = slots.get(slot_name, {})
    return str(slot.get("value", ""))


# ── Launch ────────────────────────────────────────────────────────────────────


@router.message(F.session.new)
async def handle_launch(message: Message) -> AliceResponse:
    text = (
        "Привет! Я запоминаю, где лежат вещи. "
        "Скажите: «запомни, что паспорт лежит в ящике», "
        "а потом: «где лежит паспорт?»"
    )
    return AliceResponse(response=Response(text=text))


# ── Save (IDLE) ───────────────────────────────────────────────────────────────


@router.message(F.nlu.intents["save"])
async def handle_save(
    message: Message, state: FSMContext, repo: ItemsRepository
) -> AliceResponse:
    thing = _slot_value(message, "save", "thing")
    place = _slot_value(message, "save", "place")
    user_id = _user_id(message)

    if not place:
        return AliceResponse(
            response=Response(
                text="Не могу запомнить без места. "
                "Скажите полную фразу: «запомни, что паспорт лежит в ящике»."
            )
        )

    if repo.item_exists(user_id, thing):
        items = repo.load_items(user_id)
        old_place = items.get(thing, "")
        await state.set_state(SaveForm.awaiting_confirmation)
        await state.update_data(pending_thing=thing, pending_place=place)
        old_text = f" (сейчас: {old_place})" if old_place else ""
        msg = (
            f"{thing}{old_text} уже есть в базе. "
            f"Обновить местоположение на «{place}»?"
        )
        return AliceResponse(response=Response(text=msg))

    repo.upsert_item(user_id, thing, place)
    return AliceResponse(
        response=Response(text=f"Запомнила: {thing} — {place}.")
    )


# ── Save (AWAITING_CONFIRMATION) ─────────────────────────────────────────────


@router.message(SaveForm.awaiting_confirmation)
async def handle_confirmation(
    message: Message, state: FSMContext, repo: ItemsRepository
) -> AliceResponse:
    data = await state.get_data()
    pending_thing = data.get("pending_thing", "")
    pending_place = data.get("pending_place", "")
    user_id = _user_id(message)
    intents = message.nlu.intents if message.nlu else {}

    if "YANDEX.CONFIRM" in intents:
        await state.clear()
        repo.upsert_item(user_id, pending_thing, pending_place)
        return AliceResponse(
            response=Response(
                text=f"Обновила: {pending_thing} — {pending_place}."
            )
        )

    if "YANDEX.REJECT" in intents:
        await state.clear()
        return AliceResponse(response=Response(text="Ок, оставила как есть."))

    return AliceResponse(response=Response(text="Ответьте «да» или «нет»."))


# ── Interrupt from AWAITING_CONFIRMATION ─────────────────────────────────────


@router.message(SaveForm.awaiting_confirmation, F.nlu.intents["find"])
@router.message(SaveForm.awaiting_confirmation, F.nlu.intents["delete"])
@router.message(SaveForm.awaiting_confirmation, F.nlu.intents["list"])
async def handle_interrupt(
    message: Message, state: FSMContext
) -> None:
    await state.clear()


# ── Find ──────────────────────────────────────────────────────────────────────


@router.message(F.nlu.intents["find"])
async def handle_find(
    message: Message, repo: ItemsRepository
) -> AliceResponse:
    thing = _slot_value(message, "find", "thing")
    user_id = _user_id(message)
    matches = repo.search_items(user_id, thing)

    if not matches:
        return AliceResponse(
            response=Response(text=f"Я не знаю, где лежит {thing}.")
        )

    if len(matches) == 1:
        name = matches[0]
        items = repo.load_items(user_id)
        place = items.get(name, "")
        return AliceResponse(
            response=Response(text=f"{name.capitalize()} — {place}.")
        )

    names = ", ".join(matches)
    return AliceResponse(
        response=Response(
            text=f"Найдено несколько: {names}. Уточните, что ищете."
        )
    )


# ── List ──────────────────────────────────────────────────────────────────────


@router.message(F.nlu.intents["list"])
async def handle_list(
    message: Message, repo: ItemsRepository
) -> AliceResponse:
    user_id = _user_id(message)
    names = repo.list_names(user_id)
    if not names:
        return AliceResponse(
            response=Response(text="Я пока ничего не помню.")
        )
    return AliceResponse(
        response=Response(text="У вас есть: " + ", ".join(names) + ".")
    )


# ── Delete ────────────────────────────────────────────────────────────────────


@router.message(F.nlu.intents["delete"])
async def handle_delete(
    message: Message, repo: ItemsRepository
) -> AliceResponse:
    thing = _slot_value(message, "delete", "thing")
    user_id = _user_id(message)
    items = repo.load_items(user_id)
    if thing in items:
        repo.delete_item(user_id, thing)
        return AliceResponse(response=Response(text=f"Забыла про {thing}."))
    return AliceResponse(
        response=Response(text=f"У меня нет воспоминаний про {thing}.")
    )


# ── Unknown ───────────────────────────────────────────────────────────────────


@router.message()
async def handle_unknown(message: Message) -> AliceResponse:
    command = message.command.strip() if message.command else ""
    return AliceResponse(
        response=Response(
            text=f"Не поняла: «{command}». "
            "Скажите «запомни» или «где лежит»."
        )
    )
