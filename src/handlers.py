from __future__ import annotations

import logging
from typing import Any

from aliceio import BaseMiddleware, Dispatcher, F, Router
from aliceio.fsm.context import FSMContext
from aliceio.fsm.state import State, StatesGroup
from aliceio.types import AliceResponse, Message, Response, Update

from src.nlu import DeleteIntent, FindIntent, SaveIntent
from src.repository import ItemsRepository

logger = logging.getLogger(__name__)

# ── FSM ───────────────────────────────────────────────────────────────────────


class SaveForm(StatesGroup):
    """FSM states for save flow."""

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
        """Check authorization and block unauthorized users."""
        session = event.session
        if not session or not session.user:
            return AliceResponse(response=Response(text=_NO_AUTH_TEXT))
        return await handler(event, data)


# ── Setup ─────────────────────────────────────────────────────────────────────


def setup_handlers(dp: Dispatcher) -> None:
    """Register handlers and middleware with the dispatcher."""
    dp.include_router(router)
    dp.update.outer_middleware(AuthMiddleware())


# ── Helpers ───────────────────────────────────────────────────────────────────


def _user_id(message: Message) -> str:
    return message.session.user.user_id if message.session.user else ""


# ── Launch ────────────────────────────────────────────────────────────────────


@router.message(F.session.new)
async def handle_launch(message: Message) -> AliceResponse:
    """Greet user on new session."""
    text = (
        "Привет! Я запоминаю, где лежат вещи. "
        "Скажите: «запомни, что паспорт лежит в ящике», "
        "а потом: «где лежит паспорт?»"
    )
    return AliceResponse(response=Response(text=text))


# ── Save (IDLE) ───────────────────────────────────────────────────────────────


@router.message(F.nlu.intents["save"])
async def handle_save(message: Message, state: FSMContext, repo: ItemsRepository) -> AliceResponse:
    """Save or update an item."""
    intent = SaveIntent.from_message(message)
    if intent is None:
        return AliceResponse(response=Response(text="Не распознала команду."))

    location = intent.location
    user_id = _user_id(message)

    if not location:
        return AliceResponse(
            response=Response(
                text="Не могу запомнить без места. Скажите полную фразу: «запомни, что паспорт лежит в ящике»."
            )
        )

    existing = repo.find_by_canonical_key(user_id, intent.canonical_key)
    if existing is None:
        repo.upsert_item(
            user_id,
            intent.canonical_key,
            intent.display_name,
            location,
            intent.verb,
        )
        return AliceResponse(response=Response(text=f"Запомнила: {intent.display_name} {intent.verb} {location}."))

    await state.set_state(SaveForm.awaiting_confirmation)
    await state.update_data(
        pending_canonical_key=intent.canonical_key,
        pending_display_name=intent.display_name,
        pending_location=location,
        pending_verb=intent.verb,
    )
    msg = (
        f"У вас уже есть похожая вещь «{existing.display_name}» "
        f"(сейчас: {existing.verb} {existing.location}). "
        f"Обновить на «{intent.verb} {location}»?"
    )
    return AliceResponse(response=Response(text=msg))


# ── Save (AWAITING_CONFIRMATION) ─────────────────────────────────────────────


@router.message(SaveForm.awaiting_confirmation)
async def handle_confirmation(message: Message, state: FSMContext, repo: ItemsRepository) -> AliceResponse:
    """Handle yes/no confirmation for updating an existing item."""
    fsm_data = await state.get_data()
    pending_canonical_key = fsm_data.get("pending_canonical_key", "")
    pending_display_name = fsm_data.get("pending_display_name", "")
    pending_location = fsm_data.get("pending_location", "")
    pending_verb = fsm_data.get("pending_verb", "лежит")
    user_id = _user_id(message)
    intents = message.nlu.intents if message.nlu else {}

    if "YANDEX.CONFIRM" in intents:
        await state.clear()
        repo.upsert_item(
            user_id,
            pending_canonical_key,
            pending_display_name,
            pending_location,
            pending_verb,
        )
        return AliceResponse(
            response=Response(text=f"Обновила: {pending_display_name} {pending_verb} {pending_location}.")
        )

    if "YANDEX.REJECT" in intents:
        await state.clear()
        return AliceResponse(response=Response(text="Ок, оставила как есть."))

    return AliceResponse(response=Response(text="Ответьте «да» или «нет»."))


# ── Interrupt from AWAITING_CONFIRMATION ─────────────────────────────────────


@router.message(SaveForm.awaiting_confirmation, F.nlu.intents["find"])
@router.message(SaveForm.awaiting_confirmation, F.nlu.intents["delete"])
@router.message(SaveForm.awaiting_confirmation, F.nlu.intents["list"])
async def handle_interrupt(message: Message, state: FSMContext) -> None:
    """Clear FSM state when user switches to another intent."""
    await state.clear()


# ── Find ──────────────────────────────────────────────────────────────────────


@router.message(F.nlu.intents["find"])
async def handle_find(message: Message, repo: ItemsRepository) -> AliceResponse:
    """Search for items matching a query."""
    intent = FindIntent.from_message(message)
    if intent is None:
        return AliceResponse(response=Response(text="Не распознала команду."))

    user_id = _user_id(message)
    existing = repo.find_by_canonical_key(user_id, intent.canonical_key)

    if existing is None:
        return AliceResponse(response=Response(text=f"Я не знаю, где лежит {intent.display_name}."))

    return AliceResponse(response=Response(text=f"{intent.display_name} {existing.verb} {existing.location}."))


# ── List ──────────────────────────────────────────────────────────────────────


@router.message(F.nlu.intents["list"])
async def handle_list(message: Message, repo: ItemsRepository) -> AliceResponse:
    """List all saved item names."""
    user_id = _user_id(message)
    names = repo.list_display_names(user_id)
    if not names:
        return AliceResponse(response=Response(text="Я пока ничего не помню."))
    items_str = ", ".join(names)
    return AliceResponse(response=Response(text=f"У вас есть: {items_str}."))


# ── Delete ────────────────────────────────────────────────────────────────────


@router.message(F.nlu.intents["delete"])
async def handle_delete(message: Message, repo: ItemsRepository) -> AliceResponse:
    """Delete an item by name."""
    intent = DeleteIntent.from_message(message)
    if intent is None:
        return AliceResponse(response=Response(text="Не распознала команду."))

    user_id = _user_id(message)
    existing = repo.find_by_canonical_key(user_id, intent.canonical_key)
    if existing is not None:
        repo.delete_item(user_id, intent.canonical_key)
        return AliceResponse(response=Response(text=f"Забыла про {intent.display_name}."))
    return AliceResponse(response=Response(text=f"У меня нет воспоминаний про {intent.display_name}."))


# ── Unknown ───────────────────────────────────────────────────────────────────


@router.message()
async def handle_unknown(message: Message) -> AliceResponse:
    """Fallback for unrecognized commands."""
    command = message.command.strip() if message.command else ""
    return AliceResponse(response=Response(text=f"Не поняла: «{command}». Скажите «запомни» или «где лежит»."))
