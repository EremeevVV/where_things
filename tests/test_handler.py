from __future__ import annotations

import asyncio
from typing import Any

from aliceio.fsm.context import FSMContext
from aliceio.fsm.storage.base import StorageKey
from aliceio.fsm.storage.memory import MemoryStorage
from aliceio.types import NLU, Application, Message, Session, User

from src.handlers import (
    handle_confirmation,
    handle_delete,
    handle_find,
    handle_launch,
    handle_list,
    handle_save,
    handle_unknown,
)
from src.memory_repository import InMemoryItemsRepository

# ── Helpers ───────────────────────────────────────────────────────────────────

_STORAGE = MemoryStorage()


def _make_message(
    command: str,
    *,
    user_id: str = "test_user",
    new: bool = False,
    intents: dict[str, Any] | None = None,
) -> Message:
    user = User(user_id=user_id) if user_id else None
    app = Application(application_id="test_app")
    session = Session(
        message_id=1,
        session_id="sess",
        skill_id="skill",
        application=app,
        new=new,
        user=user,
    )
    nlu = NLU(tokens=[], entities=[], intents=intents or {})
    return Message(
        session=session,
        type="SimpleUtterance",
        command=command,
        original_utterance=command,
        nlu=nlu,
    )


def _make_fsm(user_id: str = "test_user") -> FSMContext:
    key = StorageKey(
        skill_id="skill",
        user_id=user_id,
        session_id="sess",
        application_id="test_app",
    )
    return FSMContext(storage=_STORAGE, key=key)


def _intents(name: str, slots: dict[str, str]) -> dict[str, Any]:
    """Build intents dict for a single intent with slots."""
    return {name: {"slots": {k: {"value": v} for k, v in slots.items()}}}


def _save_intents(
    thing: str,
    place: str,
    preposition: str = "",
    loc_verb: str = "",
) -> dict[str, Any]:
    """Build save intent with all 4 slots."""
    slots: dict[str, str] = {"thing": thing, "place": place}
    if preposition:
        slots["preposition"] = preposition
    if loc_verb:
        slots["loc_verb"] = loc_verb
    return _intents("save", slots)


# ── Launch ────────────────────────────────────────────────────────────────────


class TestLaunch:
    """Tests for handle_launch handler."""

    def test_greeting_contains_hint(self):
        """Greeting should mention key phrases."""
        msg = _make_message("", new=True)
        result = asyncio.run(handle_launch(msg))
        text = result.response.text.lower()
        assert "запомни" in text or "где лежит" in text

    def test_has_response(self):
        """Launch should return a non-final response."""
        msg = _make_message("", new=True)
        result = asyncio.run(handle_launch(msg))
        assert result.response.text
        assert result.response.end_session is False


# ── Save ──────────────────────────────────────────────────────────────────────


class TestSave:
    """Tests for handle_save handler."""

    def test_saves_new_item(self):
        """Save a new item successfully."""
        repo = InMemoryItemsRepository()
        intents = _save_intents("паспорт", "ящике", preposition="в", loc_verb="лежит")
        msg = _make_message("запомни что паспорт лежит в ящике", intents=intents)
        result = asyncio.run(handle_save(msg, _make_fsm(), repo))
        assert "запомнила" in result.response.text.lower()
        rec = repo.find_by_canonical_key("test_user", "паспорт#")
        assert rec is not None
        assert rec.location == "в ящике"
        assert rec.verb == "лежит"

    def test_multiword_place(self):
        """Save item with multi-word place."""
        repo = InMemoryItemsRepository()
        intents = _save_intents("зарядка", "на полке у окна", loc_verb="лежит")
        msg = _make_message("запомни зарядка лежит на полке у окна", intents=intents)
        asyncio.run(handle_save(msg, _make_fsm(), repo))
        rec = repo.find_by_canonical_key("test_user", "зарядка#")
        assert rec is not None
        assert rec.location == "на полке у окна"

    def test_incomplete_asks_for_full_phrase(self):
        """Incomplete save should ask for full phrase."""
        intents = _save_intents("паспорт", "")
        msg = _make_message("запомни что паспорт", intents=intents)
        result = asyncio.run(handle_save(msg, _make_fsm(), InMemoryItemsRepository()))
        text = result.response.text.lower()
        assert "не могу запомнить" in text or "места" in text

    def test_existing_item_asks_confirmation(self):
        """Existing item should ask for confirmation."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт#", "паспорт", "в ящике", "лежит")
        intents = _save_intents("паспорт", "на полке", loc_verb="лежит")
        msg = _make_message("запомни что паспорт лежит на полке", intents=intents)
        result = asyncio.run(handle_save(msg, _make_fsm(), repo))
        text = result.response.text.lower()
        assert "похожая" in text or "обновить" in text

    def test_existing_item_keeps_old_location(self):
        """Existing item should keep old location until confirmed."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт#", "паспорт", "в ящике", "лежит")
        intents = _save_intents("паспорт", "на полке", loc_verb="лежит")
        msg = _make_message("запомни что паспорт лежит на полке", intents=intents)
        asyncio.run(handle_save(msg, _make_fsm(), repo))
        rec = repo.find_by_canonical_key("test_user", "паспорт#")
        assert rec is not None
        assert rec.location == "в ящике"


# ── Confirmation ──────────────────────────────────────────────────────────────


class TestConfirmation:
    """Tests for handle_confirmation handler."""

    def test_yes_updates(self):
        """Confirming should update the item location."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт#", "паспорт", "в ящике", "лежит")
        fsm = _make_fsm()
        intents = _save_intents("паспорт", "на полке", loc_verb="лежит")
        msg = _make_message("запомни что паспорт лежит на полке", intents=intents)
        asyncio.run(handle_save(msg, fsm, repo))
        msg_yes = _make_message("да", intents={"YANDEX.CONFIRM": {}})
        result = asyncio.run(handle_confirmation(msg_yes, fsm, repo))
        assert "обновила" in result.response.text.lower()
        rec = repo.find_by_canonical_key("test_user", "паспорт#")
        assert rec is not None
        assert rec.location == "на полке"

    def test_no_keeps_old(self):
        """Rejecting should keep old location."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт#", "паспорт", "в ящике", "лежит")
        fsm = _make_fsm()
        intents = _save_intents("паспорт", "на полке", loc_verb="лежит")
        msg = _make_message("запомни что паспорт лежит на полке", intents=intents)
        asyncio.run(handle_save(msg, fsm, repo))
        msg_no = _make_message("нет", intents={"YANDEX.REJECT": {}})
        result = asyncio.run(handle_confirmation(msg_no, fsm, repo))
        assert "оставила" in result.response.text.lower()
        rec = repo.find_by_canonical_key("test_user", "паспорт#")
        assert rec is not None
        assert rec.location == "в ящике"

    def test_unrecognized_answer(self):
        """Unrecognized answer should ask for yes/no."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт#", "паспорт", "в ящике", "лежит")
        fsm = _make_fsm()
        intents = _save_intents("паспорт", "на полке", loc_verb="лежит")
        msg = _make_message("запомни что паспорт лежит на полке", intents=intents)
        asyncio.run(handle_save(msg, fsm, repo))
        msg_weird = _make_message("maybe")
        result = asyncio.run(handle_confirmation(msg_weird, fsm, repo))
        text = result.response.text.lower()
        assert "да" in text or "нет" in text


# ── Find ──────────────────────────────────────────────────────────────────────


class TestFind:
    """Tests for handle_find handler."""

    def test_finds_exact_match(self):
        """Find exact match by name."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт#", "паспорт", "в ящике", "лежит")
        intents = _intents("find", {"thing": "паспорт"})
        msg = _make_message("где лежит паспорт", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "ящик" in result.response.text.lower()

    def test_unknown_item(self):
        """Unknown item should show not found message."""
        repo = InMemoryItemsRepository()
        intents = _intents("find", {"thing": "паспорт"})
        msg = _make_message("где лежит паспорт", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "не знаю" in result.response.text.lower()


# ── Normalize + Find ──────────────────────────────────────────────────────────


class TestNormalizeFind:
    """Tests for synonym-based find via normalization."""

    def test_find_by_synonym(self):
        """Save as смартфон, find as мобильник -> found."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "телефон#", "смартфон", "в ящике", "лежит")
        intents = _intents("find", {"thing": "мобильник"})
        msg = _make_message("где мобильник", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "ящик" in result.response.text.lower()

    def test_find_returns_intent_display_name(self):
        """Answer uses what the user said, not what's in DB."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "телефон#", "смартфон", "в ящике", "лежит")
        intents = _intents("find", {"thing": "мобильник"})
        msg = _make_message("где мобильник", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "мобильник" in result.response.text.lower()


# ── Normalize + Save ──────────────────────────────────────────────────────────


class TestNormalizeSave:
    """Tests for canonical collision via normalization."""

    def test_canonical_collision_asks_confirmation(self):
        """Save смартфон then save мобильник -> awaiting_confirmation."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "телефон#", "смартфон", "в ящике", "лежит")
        intents = _save_intents("мобильник", "на полке", loc_verb="лежит")
        msg = _make_message("запомни что мобильник лежит на полке", intents=intents)
        fsm = _make_fsm()
        result = asyncio.run(handle_save(msg, fsm, repo))
        text = result.response.text.lower()
        assert "похожая" in text or "обновить" in text

    def test_canonical_collision_confirm_keeps_new_display(self):
        """After confirm, display_name updates to the new one."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "телефон#", "смартфон", "в ящике", "лежит")
        fsm = _make_fsm()
        intents = _save_intents("мобильник", "на полке", loc_verb="лежит")
        msg = _make_message("запомни что мобильник лежит на полке", intents=intents)
        asyncio.run(handle_save(msg, fsm, repo))
        msg_yes = _make_message("да", intents={"YANDEX.CONFIRM": {}})
        asyncio.run(handle_confirmation(msg_yes, fsm, repo))
        rec = repo.find_by_canonical_key("test_user", "телефон#")
        assert rec is not None
        assert rec.display_name == "мобильник"

    def test_canonical_collision_reject_keeps_old_display(self):
        """After reject, display_name stays the old one."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "телефон#", "смартфон", "в ящике", "лежит")
        fsm = _make_fsm()
        intents = _save_intents("мобильник", "на полке", loc_verb="лежит")
        msg = _make_message("запомни что мобильник лежит на полке", intents=intents)
        asyncio.run(handle_save(msg, fsm, repo))
        msg_no = _make_message("нет", intents={"YANDEX.REJECT": {}})
        asyncio.run(handle_confirmation(msg_no, fsm, repo))
        rec = repo.find_by_canonical_key("test_user", "телефон#")
        assert rec is not None
        assert rec.display_name == "смартфон"


# ── Normalize Delete ──────────────────────────────────────────────────────────


class TestNormalizeDelete:
    """Tests for delete via synonym."""

    def test_delete_by_synonym(self):
        """Save смартфон, delete айфон -> deleted."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "телефон#", "смартфон", "в ящике", "лежит")
        intents = _intents("delete", {"thing": "айфон"})
        msg = _make_message("забудь про айфон", intents=intents)
        result = asyncio.run(handle_delete(msg, repo))
        assert "забыла" in result.response.text.lower()
        assert repo.find_by_canonical_key("test_user", "телефон#") is None


# ── Normalize Degraded ────────────────────────────────────────────────────────


class TestNormalizeDegraded:
    """Tests for degraded normalization (NO_HEAD / AMBIGUOUS_HEAD)."""

    def test_save_no_head(self):
        """Save with NO_HEAD phrase -> saved with literal key."""
        repo = InMemoryItemsRepository()
        intents = _save_intents("прекрасно", "на столе", loc_verb="лежит")
        msg = _make_message("запомни прекрасно на столе", intents=intents)
        asyncio.run(handle_save(msg, _make_fsm(), repo))
        rec = repo.find_by_canonical_key("test_user", "прекрасно")
        assert rec is not None
        assert rec.display_name == "прекрасно"

    def test_find_after_no_head_save(self):
        """Find after NO_HEAD save -> found."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "прекрасно", "прекрасно", "на столе", "лежит")
        intents = _intents("find", {"thing": "прекрасно"})
        msg = _make_message("где прекрасно", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "стол" in result.response.text.lower()

    def test_save_ambiguous_head(self):
        """Save with AMBIGUOUS_HEAD phrase -> saved with literal key."""
        repo = InMemoryItemsRepository()
        intents = _save_intents("мама мыла раму", "на полу", loc_verb="лежит")
        msg = _make_message("запомни мама мыла раму на полу", intents=intents)
        asyncio.run(handle_save(msg, _make_fsm(), repo))
        rec = repo.find_by_canonical_key("test_user", "мама мыла раму")
        assert rec is not None


# ── List ──────────────────────────────────────────────────────────────────────


class TestList:
    """Tests for handle_list handler."""

    def test_lists_names_only(self):
        """List should show only names, not locations."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт#", "паспорт", "ящик", "лежит")
        repo.upsert_item("test_user", "ключи#", "ключи", "шкаф", "висят")
        msg = _make_message("что ты помнишь")
        result = asyncio.run(handle_list(msg, repo))
        text = result.response.text.lower()
        assert "паспорт" in text
        assert "ключи" in text
        assert "ящик" not in text
        assert "шкаф" not in text

    def test_empty_list(self):
        """Empty list should show nothing remembered."""
        repo = InMemoryItemsRepository()
        msg = _make_message("что ты помнишь")
        result = asyncio.run(handle_list(msg, repo))
        assert "ничего" in result.response.text.lower()


# ── Delete ────────────────────────────────────────────────────────────────────


class TestDelete:
    """Tests for handle_delete handler."""

    def test_deletes_item(self):
        """Delete an existing item."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт#", "паспорт", "ящик", "лежит")
        intents = _intents("delete", {"thing": "паспорт"})
        msg = _make_message("забудь про паспорт", intents=intents)
        result = asyncio.run(handle_delete(msg, repo))
        assert "забыла" in result.response.text.lower()
        assert repo.find_by_canonical_key("test_user", "паспорт#") is None

    def test_delete_not_found(self):
        """Delete unknown item should show not found."""
        repo = InMemoryItemsRepository()
        intents = _intents("delete", {"thing": "телефон"})
        msg = _make_message("забудь про телефон", intents=intents)
        result = asyncio.run(handle_delete(msg, repo))
        text = result.response.text.lower()
        assert "нет" in text or "не помню" in text


# ── Unknown ───────────────────────────────────────────────────────────────────


class TestUnknown:
    """Tests for handle_unknown handler."""

    def test_unknown_command(self):
        """Unknown command should show help."""
        msg = _make_message("расскажи анекдот")
        result = asyncio.run(handle_unknown(msg))
        assert result.response.end_session is False


# ── Unauthorized ──────────────────────────────────────────────────────────────


class TestUnauthorized:
    """Tests for unauthorized user handling."""

    def test_no_user_id_on_launch(self):
        """Launch without user_id should return auth message."""
        msg = _make_message("тест", user_id="")
        result = asyncio.run(handle_launch(msg))
        assert result.response.text

    def test_no_user_id_on_find(self):
        """Find without user_id should return auth message."""
        repo = InMemoryItemsRepository()
        intents = _intents("find", {"thing": "паспорт"})
        msg = _make_message("где лежит паспорт", user_id="", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert result.response.text


# ── Fallback ──────────────────────────────────────────────────────────────────


class TestFallback:
    """Tests for fallback behavior."""

    def test_handler_returns_response(self):
        """Handler should always return a response."""
        msg = _make_message("тест")
        result = asyncio.run(handle_launch(msg))
        assert hasattr(result, "response")
        assert result.response.end_session is False
