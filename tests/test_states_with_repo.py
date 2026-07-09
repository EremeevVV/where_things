from __future__ import annotations

from main import handler
from memory_repository import InMemoryItemsRepository


def _make_event(
    command: str,
    user_id: str = "test_user",
    session_state: dict | None = None,
) -> dict:
    return {
        "session": {
            "new": False,
            "user": {"user_id": user_id},
        },
        "request": {
            "command": command,
            "original_utterance": command,
            "nlu": {"tokens": [], "entities": [], "intents": {}},
            "type": "SimpleUtterance",
        },
        "state": {
            "session": session_state or {},
            "user": {},
            "application": {},
        },
        "version": "1.0",
    }


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
        repo.delete_item("u1", "keys")  # no error

    def test_upsert_updates(self):
        repo = InMemoryItemsRepository()
        repo.upsert_item("u1", "keys", "shelf")
        repo.upsert_item("u1", "keys", "drawer")
        assert repo.load_items("u1") == {"keys": "drawer"}


class TestStatesWithInMemory:
    def test_save_full(self):
        from unittest.mock import patch

        repo = InMemoryItemsRepository()
        with patch("main._repo", repo):
            event = _make_event("запомни что паспорт лежит в ящике")
            result = handler(event, None)
            assert "запомнила" in result["response"]["text"].lower()
            assert repo.load_items("test_user") == {"паспорт": "в ящике"}

    def test_save_then_find(self):
        from unittest.mock import patch

        repo = InMemoryItemsRepository()
        with patch("main._repo", repo):
            # Save
            event1 = _make_event("запомни что паспорт лежит в ящике")
            handler(event1, None)

            # Find
            event2 = _make_event("где лежит паспорт")
            result = handler(event2, None)
            assert "ящик" in result["response"]["text"].lower()

    def test_incomplete_then_place(self):
        from unittest.mock import patch

        repo = InMemoryItemsRepository()
        with patch("main._repo", repo):
            # Incomplete save
            event1 = _make_event("запомни что паспорт")
            result1 = handler(event1, None)
            assert result1["session_state"]["dialog_state"] == "AWAITING_PLACE"

            # Answer with place
            event2 = _make_event(
                "в ящике", session_state=result1["session_state"]
            )
            result2 = handler(event2, None)
            assert "запомнила" in result2["response"]["text"].lower()
            assert repo.load_items("test_user") == {"паспорт": "в ящике"}

    def test_delete_existing(self):
        from unittest.mock import patch

        repo = InMemoryItemsRepository()
        with patch("main._repo", repo):
            repo.upsert_item("test_user", "паспорт", "ящик")

            event = _make_event("забудь про паспорт")
            result = handler(event, None)
            assert "забыла" in result["response"]["text"].lower()
            assert repo.load_items("test_user") == {}

    def test_list_items(self):
        from unittest.mock import patch

        repo = InMemoryItemsRepository()
        with patch("main._repo", repo):
            repo.upsert_item("test_user", "паспорт", "ящик")
            repo.upsert_item("test_user", "ключи", "шкаф")

            event = _make_event("что ты помнишь")
            result = handler(event, None)
            text = result["response"]["text"].lower()
            assert "паспорт" in text
            assert "ключи" in text
