from __future__ import annotations

import asyncio
from typing import Any

from aliceio.fsm.context import FSMContext
from aliceio.fsm.storage.base import StorageKey
from aliceio.fsm.storage.memory import MemoryStorage
from aliceio.types import NLU, Application, Message, Session, User

from src.handlers import (
    handle_confirmation,
    handle_find,
    handle_list,
    handle_save,
)
from src.memory_repository import InMemoryItemsRepository

_STORAGE = MemoryStorage()


def _make_message(
    command: str,
    *,
    user_id: str = "test_user",
    intents: dict[str, Any] | None = None,
) -> Message:
    user = User(user_id=user_id) if user_id else None
    app = Application(application_id="test_app")
    session = Session(
        message_id=1,
        session_id="sess",
        skill_id="skill",
        application=app,
        new=False,
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
    return {name: {"slots": {k: {"value": v} for k, v in slots.items()}}}


class TestInMemoryRepository:
    def test_save_then_find(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "keys", "shelf")
        assert repo.load_items("u1") == {"keys": "shelf"}

    def test_load_empty(self):
        repo = InMemoryItemsRepository()
        assert repo.load_items("u1") == {}

    def test_delete(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "keys", "shelf")
        repo.delete_item("u1", "keys")
        assert repo.load_items("u1") == {}

    def test_delete_nonexistent(self):
        repo = InMemoryItemsRepository()
        repo.delete_item("u1", "keys")

    def test_upsert_updates(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "keys", "shelf")
        repo.upsert_item("u1", "keys", "drawer")
        assert repo.load_items("u1") == {"keys": "drawer"}

    def test_search_items(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "паспорт", "ящик")
        repo.upsert_item("u1", "паспорт гражданина", "шкаф")
        repo.upsert_item("u1", "ключи", "шкаф")
        result = repo.search_items("u1", "паспорт")
        assert len(result) == 2

    def test_search_items_case_insensitive(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "Паспорт", "ящик")
        result = repo.search_items("u1", "паспорт")
        assert result == ["Паспорт"]

    def test_search_items_no_match(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "паспорт", "ящик")
        result = repo.search_items("u1", "телефон")
        assert result == []

    def test_list_names(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "паспорт", "ящик")
        repo.upsert_item("u1", "ключи", "шкаф")
        result = repo.list_names("u1")
        assert result == ["паспорт", "ключи"]

    def test_list_names_empty(self):
        repo = InMemoryItemsRepository()
        assert repo.list_names("u1") == []

    def test_item_exists(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "паспорт", "ящик")
        assert repo.item_exists("u1", "паспорт") is True
        assert repo.item_exists("u1", "телефон") is False

    def test_item_exists_empty(self):
        repo = InMemoryItemsRepository()
        assert repo.item_exists("u1", "паспорт") is False


class TestStatesWithInMemory:
    def test_save_full_new_item(self):
        repo = InMemoryItemsRepository()
        intents = _intents(
            "save", {"thing": "паспорт", "place": "в ящике"}
        )
        msg = _make_message(
            "запомни что паспорт лежит в ящике", intents=intents
        )
        result = asyncio.run(handle_save(msg, _make_fsm(), repo))
        assert "запомнила" in result.response.text.lower()
        assert repo.load_items("test_user") == {"паспорт": "в ящике"}

    def test_save_no_place(self):
        intents = _intents("save", {"thing": "паспорт", "place": ""})
        msg = _make_message("запомни паспорт", intents=intents)
        result = asyncio.run(handle_save(msg, _make_fsm(), InMemoryItemsRepository()))
        text = result.response.text.lower()
        assert "не могу запомнить" in text or "места" in text

    def test_save_existing_asks_confirm(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "в ящике")
        intents = _intents(
            "save", {"thing": "паспорт", "place": "на полке"}
        )
        msg = _make_message(
            "запомни что паспорт лежит на полке", intents=intents
        )
        result = asyncio.run(handle_save(msg, _make_fsm(), repo))
        text = result.response.text.lower()
        assert "уже есть" in text or "обновить" in text
        assert repo.load_items("test_user") == {"паспорт": "в ящике"}

    def test_save_confirm_yes_updates(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "в ящике")
        fsm = _make_fsm()
        intents = _intents(
            "save", {"thing": "паспорт", "place": "на полке"}
        )
        msg = _make_message(
            "запомни что паспорт лежит на полке", intents=intents
        )
        asyncio.run(handle_save(msg, fsm, repo))
        msg_yes = _make_message("да", intents={"YANDEX.CONFIRM": {}})
        result = asyncio.run(handle_confirmation(msg_yes, fsm, repo))
        assert "обновила" in result.response.text.lower()
        assert repo.load_items("test_user") == {"паспорт": "на полке"}

    def test_save_confirm_no_keeps_old(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "в ящике")
        fsm = _make_fsm()
        intents = _intents(
            "save", {"thing": "паспорт", "place": "на полке"}
        )
        msg = _make_message(
            "запомни что паспорт лежит на полке", intents=intents
        )
        asyncio.run(handle_save(msg, fsm, repo))
        msg_no = _make_message("нет", intents={"YANDEX.REJECT": {}})
        result = asyncio.run(handle_confirmation(msg_no, fsm, repo))
        assert "оставила" in result.response.text.lower()
        assert repo.load_items("test_user") == {"паспорт": "в ящике"}

    def test_find_substring(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "зарядка для телефона", "на полке")
        intents = _intents("find", {"thing": "заряд"})
        msg = _make_message("где заряд", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "полк" in result.response.text.lower()

    def test_find_multiple(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "ящик")
        repo.upsert_item("test_user", "паспорт гражданина", "шкаф")
        intents = _intents("find", {"thing": "паспорт"})
        msg = _make_message("где паспорт", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "найдено несколько" in result.response.text.lower()

    def test_list_names_only(self):
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
