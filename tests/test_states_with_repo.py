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


class TestInMemoryRepository:
    """Tests for InMemoryItemsRepository."""

    def test_save_then_find(self):
        """Save and then find an item."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "keys", "on shelf", "sit")
        assert repo.load_items("u1") == {"keys": ("sit", "on shelf")}

    def test_load_empty(self):
        """Load items for empty user."""
        repo = InMemoryItemsRepository()
        assert repo.load_items("u1") == {}

    def test_delete(self):
        """Delete an item."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "keys", "on shelf", "sit")
        repo.delete_item("u1", "keys")
        assert repo.load_items("u1") == {}

    def test_delete_nonexistent(self):
        """Delete nonexistent item should not raise."""
        repo = InMemoryItemsRepository()
        repo.delete_item("u1", "keys")

    def test_upsert_updates(self):
        """Upsert should update existing item."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "keys", "on shelf", "sit")
        repo.upsert_item("u1", "keys", "in drawer", "lay")
        assert repo.load_items("u1") == {"keys": ("lay", "in drawer")}

    def test_search_items(self):
        """Search items by exact name."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "паспорт", "ящик", "лежит")
        repo.upsert_item("u1", "паспорт гражданина", "шкаф", "лежит")
        repo.upsert_item("u1", "ключи", "шкаф", "висят")
        result = repo.search_items("u1", "паспорт")
        assert len(result) == 1
        assert result == ["паспорт"]

    def test_search_items_case_insensitive(self):
        """Search should be case-insensitive."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "Паспорт", "ящик", "лежит")
        result = repo.search_items("u1", "паспорт")
        assert result == ["Паспорт"]

    def test_search_items_no_match(self):
        """Search with no match should return empty list."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "паспорт", "ящик", "лежит")
        result = repo.search_items("u1", "телефон")
        assert result == []

    def test_list_names(self):
        """List item names."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "паспорт", "ящик", "лежит")
        repo.upsert_item("u1", "ключи", "шкаф", "висят")
        result = repo.list_names("u1")
        assert result == ["паспорт", "ключи"]

    def test_list_names_empty(self):
        """List names for empty user."""
        repo = InMemoryItemsRepository()
        assert repo.list_names("u1") == []

    def test_item_exists(self):
        """Check if item exists."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "паспорт", "ящик", "лежит")
        assert repo.item_exists("u1", "паспорт") is True
        assert repo.item_exists("u1", "телефон") is False

    def test_item_exists_empty(self):
        """Check if item exists for empty user."""
        repo = InMemoryItemsRepository()
        assert repo.item_exists("u1", "паспорт") is False


class TestStatesWithInMemory:
    """Integration tests with InMemoryItemsRepository."""

    def test_save_full_new_item(self):
        """Save a complete new item."""
        repo = InMemoryItemsRepository()
        intents = _save_intents("паспорт", "ящике", preposition="в", loc_verb="лежит")
        msg = _make_message("запомни что паспорт лежит в ящике", intents=intents)
        result = asyncio.run(handle_save(msg, _make_fsm(), repo))
        assert "запомнила" in result.response.text.lower()
        assert repo.load_items("test_user") == {"паспорт": ("лежит", "в ящике")}

    def test_save_no_place(self):
        """Save without place should ask for full phrase."""
        intents = _save_intents("паспорт", "")
        msg = _make_message("запомни паспорт", intents=intents)
        result = asyncio.run(handle_save(msg, _make_fsm(), InMemoryItemsRepository()))
        text = result.response.text.lower()
        assert "не могу запомнить" in text or "места" in text

    def test_save_existing_asks_confirm(self):
        """Existing item should ask for confirmation."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "в ящике", "лежит")
        intents = _save_intents("паспорт", "на полке", loc_verb="лежит")
        msg = _make_message("запомни что паспорт лежит на полке", intents=intents)
        result = asyncio.run(handle_save(msg, _make_fsm(), repo))
        text = result.response.text.lower()
        assert "уже есть" in text or "обновить" in text
        assert repo.load_items("test_user") == {"паспорт": ("лежит", "в ящике")}

    def test_save_confirm_yes_updates(self):
        """Confirming should update item location."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "в ящике", "лежит")
        fsm = _make_fsm()
        intents = _save_intents("паспорт", "на полке", loc_verb="лежит")
        msg = _make_message("запомни что паспорт лежит на полке", intents=intents)
        asyncio.run(handle_save(msg, fsm, repo))
        msg_yes = _make_message("да", intents={"YANDEX.CONFIRM": {}})
        result = asyncio.run(handle_confirmation(msg_yes, fsm, repo))
        assert "обновила" in result.response.text.lower()
        assert repo.load_items("test_user") == {"паспорт": ("лежит", "на полке")}

    def test_save_confirm_no_keeps_old(self):
        """Rejecting should keep old location."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "в ящике", "лежит")
        fsm = _make_fsm()
        intents = _save_intents("паспорт", "на полке", loc_verb="лежит")
        msg = _make_message("запомни что паспорт лежит на полке", intents=intents)
        asyncio.run(handle_save(msg, fsm, repo))
        msg_no = _make_message("нет", intents={"YANDEX.REJECT": {}})
        result = asyncio.run(handle_confirmation(msg_no, fsm, repo))
        assert "оставила" in result.response.text.lower()
        assert repo.load_items("test_user") == {"паспорт": ("лежит", "в ящике")}

    def test_find_exact(self):
        """Find by exact name."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "зарядка для телефона", "на полке", "лежит")
        intents = _intents("find", {"thing": "зарядка для телефона"})
        msg = _make_message("где зарядка для телефона", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "полк" in result.response.text.lower()

    def test_find_exact_not_substring(self):
        """Exact match should not find substrings."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "зарядка для телефона", "на полке", "лежит")
        intents = _intents("find", {"thing": "зарядка"})
        msg = _make_message("где зарядка", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "не знаю" in result.response.text.lower()

    def test_find_multiple(self):
        """Exact match should find only the exact name."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "ящик", "лежит")
        repo.upsert_item("test_user", "паспорт гражданина", "шкаф", "лежит")
        intents = _intents("find", {"thing": "паспорт"})
        msg = _make_message("где паспорт", intents=intents)
        result = asyncio.run(handle_find(msg, repo))
        assert "ящик" in result.response.text.lower()

    def test_list_names_only(self):
        """List should show only names."""
        repo = InMemoryItemsRepository()
        repo.upsert_item("test_user", "паспорт", "ящик", "лежит")
        repo.upsert_item("test_user", "ключи", "шкаф", "висят")
        msg = _make_message("что ты помнишь")
        result = asyncio.run(handle_list(msg, repo))
        text = result.response.text.lower()
        assert "паспорт" in text
        assert "ключи" in text
        assert "ящик" not in text
        assert "шкаф" not in text
