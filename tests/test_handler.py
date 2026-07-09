from __future__ import annotations

from unittest.mock import patch

from main import handler
from nlu import Intent, parse_intent

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_event(
    command: str,
    user_id: str = "test_user",
    session_state: dict | None = None,
    items: dict | None = None,
) -> dict:
    """Build a minimal Yandex Dialogs event for testing."""
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


# ── parse_intent ──────────────────────────────────────────────────────────────


class TestParseIntent:
    def test_save_basic(self):
        intent, slots = parse_intent("запомни что паспорт лежит в ящике")
        assert intent == Intent.SAVE
        assert slots["thing"] == "паспорт"
        assert slots["place"] == "в ящике"

    def test_save_without_that(self):
        intent, slots = parse_intent("запомни паспорт лежит в ящике")
        assert intent == Intent.SAVE
        assert slots["thing"] == "паспорт"
        assert slots["place"] == "в ящике"

    def test_save_multiword_place(self):
        intent, slots = parse_intent(
            "запомни что зарядка лежит на полке у окна"
        )
        assert intent == Intent.SAVE
        assert slots["thing"] == "зарядка"
        assert slots["place"] == "на полке у окна"

    def test_save_incomplete(self):
        intent, slots = parse_intent("запомни что паспорт")
        assert intent == Intent.SAVE
        assert slots["thing"] == "паспорт"
        assert slots["place"] == ""

    def test_find_basic(self):
        intent, slots = parse_intent("где лежит паспорт")
        assert intent == Intent.FIND
        assert slots["thing"] == "паспорт"

    def test_find_short(self):
        intent, slots = parse_intent("где паспорт")
        assert intent == Intent.FIND
        assert slots["thing"] == "паспорт"

    def test_list(self):
        intent, slots = parse_intent("что ты помнишь")
        assert intent == Intent.LIST
        assert slots == {}

    def test_delete(self):
        intent, slots = parse_intent("забудь про паспорт")
        assert intent == Intent.DELETE
        assert slots["thing"] == "паспорт"

    def test_delete_short(self):
        intent, slots = parse_intent("забудь паспорт")
        assert intent == Intent.DELETE
        assert slots["thing"] == "паспорт"

    def test_unknown(self):
        intent, slots = parse_intent("расскажи анекдот")
        assert intent == Intent.UNKNOWN


# ── Launch ────────────────────────────────────────────────────────────────────


class TestLaunch:
    def test_greeting_contains_hint(self, event_launch):
        result = handler(event_launch, None)
        assert result["response"]["end_session"] is False
        text = result["response"]["text"].lower()
        assert "запомни" in text or "где лежит" in text

    def test_version(self, event_launch):
        result = handler(event_launch, None)
        assert result["version"] == "1.0"

    def test_has_tts(self, event_launch):
        result = handler(event_launch, None)
        assert "tts" in result["response"]


# ── Save ──────────────────────────────────────────────────────────────────────


class TestSave:
    @patch("main._repo")
    def test_saves_to_ydb(self, mock_repo):
        event = _make_event("запомни что паспорт лежит в верхнем ящике стола")
        result = handler(event, None)
        mock_repo.upsert_item.assert_called_once_with(
            "test_user", "паспорт", "в верхнем ящике стола"
        )
        assert "запомнила" in result["response"]["text"].lower()

    @patch("main._repo")
    def test_confirmation_text(self, mock_repo):
        event = _make_event("запомни что паспорт лежит в ящике")
        result = handler(event, None)
        text = result["response"]["text"].lower()
        assert "запомнила" in text
        assert "паспорт" in text

    @patch("main._repo")
    def test_multiword_place(self, mock_repo):
        event = _make_event("запомни что зарядка лежит на полке у окна")
        handler(event, None)
        mock_repo.upsert_item.assert_called_once_with(
            "test_user", "зарядка", "на полке у окна"
        )

    def test_incomplete_asks_place(self):
        event = _make_event("запомни что паспорт")
        result = handler(event, None)
        text = result["response"]["text"].lower()
        assert "где" in text or "место" in text
        assert result["session_state"]["dialog_state"] == "AWAITING_PLACE"
        assert result["session_state"]["pending_thing"] == "паспорт"


# ── Find ──────────────────────────────────────────────────────────────────────


class TestFind:
    @patch("main._repo")
    def test_finds_saved_item(self, mock_repo):
        mock_repo.load_items.return_value = {"паспорт": "в ящике"}
        event = _make_event("где лежит паспорт")
        result = handler(event, None)
        text = result["response"]["text"].lower()
        assert "ящик" in text

    @patch("main._repo")
    def test_unknown_item(self, mock_repo):
        mock_repo.load_items.return_value = {}
        event = _make_event("где лежит паспорт")
        result = handler(event, None)
        text = result["response"]["text"].lower()
        assert "не знаю" in text


# ── List ──────────────────────────────────────────────────────────────────────


class TestList:
    @patch("main._repo")
    def test_lists_items(self, mock_repo):
        mock_repo.load_items.return_value = {"паспорт": "ящик", "ключи": "шкаф"}
        event = _make_event("что ты помнишь")
        result = handler(event, None)
        text = result["response"]["text"].lower()
        assert "паспорт" in text
        assert "ключи" in text

    @patch("main._repo")
    def test_empty_list(self, mock_repo):
        mock_repo.load_items.return_value = {}
        event = _make_event("что ты помнишь")
        result = handler(event, None)
        assert "ничего" in result["response"]["text"].lower()


# ── Delete ────────────────────────────────────────────────────────────────────


class TestDelete:
    @patch("main._repo")
    def test_deletes_item(self, mock_repo):
        mock_repo.load_items.return_value = {"паспорт": "ящик", "ключи": "шкаф"}
        event = _make_event("забудь про паспорт")
        result = handler(event, None)
        mock_repo.delete_item.assert_called_once_with("test_user", "паспорт")
        assert "забыла" in result["response"]["text"].lower()

    @patch("main._repo")
    def test_delete_not_found(self, mock_repo):
        mock_repo.load_items.return_value = {}
        event = _make_event("забудь про телефон")
        result = handler(event, None)
        text = result["response"]["text"].lower()
        assert "нет" in text or "не помню" in text


# ── Unknown ───────────────────────────────────────────────────────────────────


class TestUnknown:
    def test_unknown_command(self):
        event = _make_event("расскажи анекдот")
        result = handler(event, None)
        assert "response" in result
        assert result["response"]["end_session"] is False


# ── Unauthorized ──────────────────────────────────────────────────────────────


class TestUnauthorized:
    def test_no_user_id_shows_auth_error(self):
        event = _make_event("запомни что паспорт лежит в ящике", user_id="")
        result = handler(event, None)
        text = result["response"]["text"].lower()
        assert "авториз" in text

    def test_no_user_id_on_find(self):
        event = _make_event("где лежит паспорт", user_id="")
        result = handler(event, None)
        text = result["response"]["text"].lower()
        assert "авториз" in text


# ── State machine ─────────────────────────────────────────────────────────────


class TestStateMachine:
    """Тесты многошагового диалога (машина состояний)."""

    def test_incomplete_saves_transitions_to_awaiting(self):
        event = _make_event("запомни что паспорт")
        result = handler(event, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") == "AWAITING_PLACE"
        assert state.get("pending_thing") == "паспорт"
        assert state.get("state_visits") == 1

    @patch("main._repo")
    def test_awaiting_place_saves_on_answer(self, mock_repo):
        event = _make_event(
            "в ящике стола",
            session_state={
                "dialog_state": "AWAITING_PLACE",
                "pending_thing": "паспорт",
                "state_visits": 1,
            },
        )
        result = handler(event, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") is None or state.get(
            "dialog_state"
        ) == "IDLE"
        mock_repo.upsert_item.assert_called_once_with(
            "test_user", "паспорт", "в ящике стола"
        )
        assert "запомнила" in result["response"]["text"].lower()

    @patch("main._repo")
    def test_awaiting_place_saves_short_answer(self, mock_repo):
        # "привет" — 6 символов, >= 2, считается местом
        event = _make_event(
            "привет",
            session_state={
                "dialog_state": "AWAITING_PLACE",
                "pending_thing": "паспорт",
                "state_visits": 1,
            },
        )
        result = handler(event, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") is None or state.get(
            "dialog_state"
        ) == "IDLE"
        mock_repo.upsert_item.assert_called_once_with(
            "test_user", "паспорт", "привет"
        )

    def test_awaiting_place_one_char_gives_hint(self):
        event = _make_event(
            "а",
            session_state={
                "dialog_state": "AWAITING_PLACE",
                "pending_thing": "паспорт",
                "state_visits": 1,
            },
        )
        result = handler(event, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") == "AWAITING_PLACE"
        assert state.get("state_visits") == 2

    def test_awaiting_place_second_hint_has_example(self):
        event = _make_event(
            "а",
            session_state={
                "dialog_state": "AWAITING_PLACE",
                "pending_thing": "паспорт",
                "state_visits": 2,
            },
        )
        result = handler(event, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") == "AWAITING_PLACE"
        assert state.get("state_visits") == 3
        text = result["response"]["text"].lower()
        assert "пример" in text

    @patch("main._repo")
    def test_awaiting_place_breaks_with_find(self, mock_repo):
        mock_repo.load_items.return_value = {}
        event = _make_event(
            "где лежит ключи",
            session_state={
                "dialog_state": "AWAITING_PLACE",
                "pending_thing": "паспорт",
                "state_visits": 1,
            },
        )
        result = handler(event, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") is None or state.get(
            "dialog_state"
        ) == "IDLE"

    @patch("main._repo")
    def test_awaiting_place_breaks_with_delete(self, mock_repo):
        mock_repo.load_items.return_value = {}
        event = _make_event(
            "забудь про паспорт",
            session_state={
                "dialog_state": "AWAITING_PLACE",
                "pending_thing": "ключи",
                "state_visits": 1,
            },
        )
        result = handler(event, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") is None or state.get(
            "dialog_state"
        ) == "IDLE"
        text = result["response"]["text"].lower()
        assert "забыла" in text or "нет" in text or "не помню" in text

    @patch("main._repo")
    def test_awaiting_place_new_save_full(self, mock_repo):
        event = _make_event(
            "запомни что телефон лежит в рюкзаке",
            session_state={
                "dialog_state": "AWAITING_PLACE",
                "pending_thing": "паспорт",
                "state_visits": 1,
            },
        )
        result = handler(event, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") is None or state.get(
            "dialog_state"
        ) == "IDLE"
        mock_repo.upsert_item.assert_called_once_with(
            "test_user", "телефон", "в рюкзаке"
        )
        assert "запомнила" in result["response"]["text"].lower()

    def test_awaiting_place_new_save_incomplete(self):
        event = _make_event(
            "запомни что телефон",
            session_state={
                "dialog_state": "AWAITING_PLACE",
                "pending_thing": "паспорт",
                "state_visits": 1,
            },
        )
        result = handler(event, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") == "AWAITING_PLACE"
        assert state.get("pending_thing") == "телефон"
        assert state.get("state_visits") == 1

    @patch("main._repo")
    def test_full_flow_incomplete_then_place(self, mock_repo):
        """Интеграционный тест: два вызова handler подряд."""
        event1 = _make_event("запомни что паспорт")
        result1 = handler(event1, None)
        assert result1["session_state"]["dialog_state"] == "AWAITING_PLACE"
        assert result1["session_state"]["pending_thing"] == "паспорт"

        # Второй вызов — отвечаем местом
        event2 = _make_event(
            "в ящике стола",
            session_state=result1["session_state"],
        )
        handler(event2, None)
        mock_repo.upsert_item.assert_called_once_with(
            "test_user", "паспорт", "в ящике стола"
        )

    @patch("main._repo")
    def test_full_flow_breaks_with_find(self, mock_repo):
        """Интеграционный тест: прерываем сохранение командой FIND."""
        mock_repo.load_items.return_value = {}
        event1 = _make_event("запомни что паспорт")
        result1 = handler(event1, None)
        assert result1["session_state"]["dialog_state"] == "AWAITING_PLACE"

        event2 = _make_event(
            "где лежит ключи",
            session_state=result1["session_state"],
        )
        result2 = handler(event2, None)
        assert result2["session_state"].get("dialog_state") is None
        assert result2["session_state"].get("pending_thing") is None

    @patch("main._repo")
    def test_regression_save_full(self, mock_repo):
        """Регрессия: полное сохранение работает как раньше."""
        event = _make_event("запомни что паспорт лежит в ящике")
        result = handler(event, None)
        mock_repo.upsert_item.assert_called_once_with("test_user", "паспорт", "в ящике")
        assert "запомнила" in result["response"]["text"].lower()

    @patch("main._repo")
    def test_regression_find(self, mock_repo):
        """Регрессия: поиск работает как раньше."""
        mock_repo.load_items.return_value = {"паспорт": "в ящике"}
        event = _make_event("где лежит паспорт")
        result = handler(event, None)
        assert "ящик" in result["response"]["text"].lower()

    @patch("main._repo")
    def test_regression_list(self, mock_repo):
        """Регрессия: список работает как раньше."""
        mock_repo.load_items.return_value = {"паспорт": "ящик", "ключи": "шкаф"}
        event = _make_event("что ты помнишь")
        result = handler(event, None)
        text = result["response"]["text"].lower()
        assert "паспорт" in text
        assert "ключи" in text

    @patch("main._repo")
    def test_regression_delete(self, mock_repo):
        """Регрессия: удаление работает как раньше."""
        mock_repo.load_items.return_value = {"паспорт": "ящик", "ключи": "шкаф"}
        event = _make_event("забудь про паспорт")
        result = handler(event, None)
        mock_repo.delete_item.assert_called_once_with("test_user", "паспорт")
        assert "забыла" in result["response"]["text"].lower()


# ── Fallback on error ────────────────────────────────────────────────────────


class TestFallback:
    @patch("main._handle", side_effect=ValueError("boom"))
    def test_fallback_on_exception(self, _mock):
        event = _make_event("запомни что паспорт лежит в ящике")
        result = handler(event, None)
        assert result["response"]["end_session"] is False
        assert "извините" in result["response"]["text"].lower()
        assert result["version"] == "1.0"
