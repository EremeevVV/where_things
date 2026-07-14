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


# ── Launch ────────────────────────────────────────────────────────────────────


class TestLaunch:
    def test_greeting_contains_hint(self):
        msg = _make_message("", new=True)
        result = asyncio.run(handle_launch(msg))
        text = result.response.text.lower()
        assert "запомни" in text or "где лежит" in text

    def test_has_response(self):
        msg = _make_message("", new=True)
        result = asyncio.run(handle_launch(msg))
        assert result.response.text
        assert result.response.end_session is False


# ── Save ──────────────────────────────────────────────────────────────────────


class TestSave:
    def test_saves_new_item(self):
        repo = InMemoryItemsRepository()
        intents = _intents("save", {"thing": "паспорт", "place": "в ящике"})
        msg = _make_message(
            "запомни что паспорт лежит в ящике", intents=intents
        )
        result = asyncio.run(handle_save(msg, _make_fsm(), repo))
        assert "запомнила" in result.response.text.lower()
        assert repo.load_items("test_user") == {"паспорт": "в ящике"}

    def test_multiword_place(self):
        repo = InMemoryItemsRepository()
        intents = _intents(
            "save", {"thing": "зарядка", "place": "на полке у окна"}
        )
        msg = _make_message(
            "запомни зарядка лежит на полке у окна", intents=intents
        )
        asyncio.run(handle_save(msg, _make_fsm(), repo))
        assert repo.load_items("test_user") == {
            "зарядка": "на полке у окна"
        }

    def test_incomplete_asks_for_full_phrase(self):
        intents = _intents("save", {"thing": "паспорт", "place": ""})
        msg = _make_message("запомни что паспорт", intents=intents)
        result = asyncio.run(handle_save(msg, _make_fsm(), InMemoryItemsRepository()))
        text = result.response.text.lower()
        assert "не могу запомнить" in text or "места" in text

    def test_existing_item_asks_confirmation(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "в ящике")
        intents = _intents("save", {"thing": "паспорт", "place": "на полке"})
        msg = _make_message(
            "запомни что паспорт лежит на полке", intents=intents
        )
        result = asyncio.run(handle_save(msg, _make_fsm(), repo))
        text = result.response.text.lower()
        assert "уже есть" in text or "обновить" in text

    def test_existing_item_keeps_old_location(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "в ящике")
        intents = _intents("save", {"thing": "паспорт", "place": "на полке"})
        msg = _make_message(
            "запомни что паспорт лежит на полке", intents=intents
        )
        asyncio.run(handle_save(msg, _make_fsm(), repo))
        assert repo.load_items("test_user") == {"паспорт": "в ящике"}


# ── Confirmation ──────────────────────────────────────────────────────────────


class TestConfirmation:
    def test_yes_updates(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "в ящике")
        fsm = _make_fsm()
        intents = _intents("save", {"thing": "паспорт", "place": "на полке"})
        msg = _make_message(
            "запомни что паспорт лежит на полке", intents=intents
        )
        asyncio.run(handle_save(msg, fsm, repo))
        msg_yes = _make_message("да", intents={"YANDEX.CONFIRM": {}})
        result = asyncio.run(handle_confirmation(msg_yes, fsm, repo))
        assert "обновила" in result.response.text.lower()
        assert repo.load_items("test_user") == {"паспорт": "на полке"}

    def test_no_keeps_old(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "в ящике")
        fsm = _make_fsm()
        intents = _intents("save", {"thing": "паспорт", "place": "на полке"})
        msg = _make_message(
            "запомни что паспорт лежит на полке", intents=intents
        )
        asyncio.run(handle_save(msg, fsm, repo))
        msg_no = _make_message("нет", intents={"YANDEX.REJECT": {}})
        result = asyncio.run(handle_confirmation(msg_no, fsm, repo))
        assert "оставила" in result.response.text.lower()
        assert repo.load_items("test_user") == {"паспорт": "в ящике"}

    def test_unrecognized_answer(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "в ящике")
        fsm = _make_fsm()
        intents = _intents("save", {"thing": "паспорт", "place": "на полке"})
        msg = _make_message(
            "запомни что паспорт лежит на полке", intents=intents
        )
        asyncio.run(handle_save(msg, fsm, repo))
        msg_weird = _make_message("maybe")
        result = asyncio.run(handle_confirmation(msg_weird, fsm, repo))
        text = result.response.text.lower()
        assert "да" in text or "нет" in text


# ── Find ──────────────────────────────────────────────────────────────────────


class TestFind:
    def test_finds_exact_match(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "в ящике")
        intents = _intents("find", {"thing": "паспорт"})
        msg = _make_message("где лежит паспорт", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "ящик" in result.response.text.lower()

    def test_finds_substring(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "зарядка для телефона", "на полке")
        intents = _intents("find", {"thing": "заряд"})
        msg = _make_message("где заряд", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "полк" in result.response.text.lower()

    def test_substring_case_insensitive(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "Паспорт", "в ящике")
        intents = _intents("find", {"thing": "паспорт"})
        msg = _make_message("где паспорт", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "ящик" in result.response.text.lower()

    def test_multiple_matches(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "ящик")
        repo.upsert_item("test_user", "паспорт гражданина", "шкаф")
        intents = _intents("find", {"thing": "паспорт"})
        msg = _make_message("где паспорт", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        text = result.response.text.lower()
        assert "найдено несколько" in text

    def test_unknown_item(self):
        repo = InMemoryItemsRepository()
        intents = _intents("find", {"thing": "паспорт"})
        msg = _make_message("где лежит паспорт", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "не знаю" in result.response.text.lower()


# ── List ──────────────────────────────────────────────────────────────────────


class TestList:
    def test_lists_names_only(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "ящик")
        repo.upsert_item("test_user", "ключи", "шкаф")
        msg = _make_message("что ты помнишь")
        result = asyncio.run(handle_list(msg, repo))
        text = result.response.text.lower()
        assert "паспорт" in text
        assert "ключи" in text
        assert "ящик" not in text
        assert "шкаф" not in text

    def test_empty_list(self):
        repo = InMemoryItemsRepository()
        msg = _make_message("что ты помнишь")
        result = asyncio.run(handle_list(msg, repo))
        assert "ничего" in result.response.text.lower()


# ── Delete ────────────────────────────────────────────────────────────────────


class TestDelete:
    def test_deletes_item(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "ящик")
        intents = _intents("delete", {"thing": "паспорт"})
        msg = _make_message("забудь про паспорт", intents=intents)
        result = asyncio.run(handle_delete(msg, repo))
        assert "забыла" in result.response.text.lower()
        assert repo.load_items("test_user") == {}

    def test_delete_not_found(self):
        repo = InMemoryItemsRepository()
        intents = _intents("delete", {"thing": "телефон"})
        msg = _make_message("забудь про телефон", intents=intents)
        result = asyncio.run(handle_delete(msg, repo))
        text = result.response.text.lower()
        assert "нет" in text or "не помню" in text


# ── Unknown ───────────────────────────────────────────────────────────────────


class TestUnknown:
    def test_unknown_command(self):
        msg = _make_message("расскажи анекдот")
        result = asyncio.run(handle_unknown(msg))
        assert result.response.end_session is False


# ── Unauthorized ──────────────────────────────────────────────────────────────


class TestUnauthorized:
    def test_no_user_id_on_launch(self):
        msg = _make_message("тест", user_id="")
        result = asyncio.run(handle_launch(msg))
        assert result.response.text

    def test_no_user_id_on_find(self):
        repo = InMemoryItemsRepository()
        intents = _intents("find", {"thing": "паспорт"})
        msg = _make_message("где лежит паспорт", user_id="", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert result.response.text


# ── Fallback ──────────────────────────────────────────────────────────────────


class TestFallback:
    def test_handler_returns_response(self):
        msg = _make_message("тест")
        result = asyncio.run(handle_launch(msg))
        assert hasattr(result, "response")
        assert result.response.end_session is False
