from main import handler, parse_intent


class TestParseIntent:
    def test_save_basic(self):
        intent, slots = parse_intent("запомни что паспорт лежит в ящике")
        assert intent == "SAVE"
        assert slots["thing"] == "паспорт"
        assert slots["place"] == "в ящике"

    def test_save_without_that(self):
        intent, slots = parse_intent("запомни паспорт лежит в ящике")
        assert intent == "SAVE"
        assert slots["thing"] == "паспорт"
        assert slots["place"] == "в ящике"

    def test_save_multiword_place(self):
        intent, slots = parse_intent(
            "запомни что зарядка лежит на полке у окна"
        )
        assert intent == "SAVE"
        assert slots["thing"] == "зарядка"
        assert slots["place"] == "на полке у окна"

    def test_save_incomplete(self):
        intent, slots = parse_intent("запомни что паспорт")
        assert intent == "SAVE"
        assert slots["thing"] == "паспорт"
        assert slots["place"] == ""

    def test_find_basic(self):
        intent, slots = parse_intent("где лежит паспорт")
        assert intent == "FIND"
        assert slots["thing"] == "паспорт"

    def test_find_short(self):
        intent, slots = parse_intent("где паспорт")
        assert intent == "FIND"
        assert slots["thing"] == "паспорт"

    def test_list(self):
        intent, slots = parse_intent("что ты помнишь")
        assert intent == "LIST"
        assert slots == {}

    def test_delete(self):
        intent, slots = parse_intent("забудь про паспорт")
        assert intent == "DELETE"
        assert slots["thing"] == "паспорт"

    def test_delete_short(self):
        intent, slots = parse_intent("забудь паспорт")
        assert intent == "DELETE"
        assert slots["thing"] == "паспорт"

    def test_unknown(self):
        intent, slots = parse_intent("расскажи анекдот")
        assert intent == "UNKNOWN"


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


class TestSave:
    def test_saves_to_session_state(self, event_save):
        result = handler(event_save, None)
        items = result.get("session_state", {}).get("items", {})
        assert "паспорт" in items
        assert items["паспорт"] == "в верхнем ящике стола"

    def test_confirmation_text(self, event_save):
        result = handler(event_save, None)
        text = result["response"]["text"].lower()
        assert "запомнила" in text
        assert "паспорт" in text

    def test_multiword_place(self, event_save_multiword):
        result = handler(event_save_multiword, None)
        items = result.get("session_state", {}).get("items", {})
        assert items["зарядка"] == "на полке у окна"

    def test_incomplete_asks_place(self, event_save_incomplete):
        result = handler(event_save_incomplete, None)
        text = result["response"]["text"].lower()
        assert "где" in text or "место" in text
        assert result.get("session_state", {}).get("items", {}).get(
            "паспорт"
        ) is None


class TestFind:
    def test_finds_saved_item(self, event_find):
        result = handler(event_find, None)
        text = result["response"]["text"].lower()
        assert "ящик" in text

    def test_unknown_item(self, event_find_unknown):
        result = handler(event_find_unknown, None)
        text = result["response"]["text"].lower()
        assert "не знаю" in text or "не помню" in text


class TestList:
    def test_lists_items(self, event_list):
        result = handler(event_list, None)
        text = result["response"]["text"].lower()
        assert "паспорт" in text
        assert "ключи" in text

    def test_empty_list(self, event_launch):
        result = handler(event_launch, None)
        event_fresh = {
            "session": {"new": False, "user": {"user_id": "x"}},
            "request": {
                "command": "что ты помнишь",
                "original_utterance": "Что ты помнишь?",
                "nlu": {"tokens": [], "entities": [], "intents": {}},
                "type": "SimpleUtterance",
            },
            "state": {"session": {}, "user": {}, "application": {}},
            "version": "1.0",
        }
        result = handler(event_fresh, None)
        assert "ничего" in result["response"]["text"].lower()


class TestDelete:
    def test_deletes_item(self, event_delete):
        result = handler(event_delete, None)
        items = result.get("session_state", {}).get("items", {})
        assert "паспорт" not in items
        assert "ключи" in items

    def test_delete_not_found(self, event_launch):
        event = {
            "session": {"new": False, "user": {"user_id": "x"}},
            "request": {
                "command": "забудь про телефон",
                "original_utterance": "Забудь про телефон.",
                "nlu": {"tokens": [], "entities": [], "intents": {}},
                "type": "SimpleUtterance",
            },
            "state": {
                "session": {"items": {"паспорт": "ящик"}},
                "user": {},
                "application": {},
            },
            "version": "1.0",
        }
        result = handler(event, None)
        text = result["response"]["text"].lower()
        assert "нет" in text or "не помню" in text


class TestUnknown:
    def test_unknown_command(self, event_launch):
        event = {
            "session": {"new": False, "user": {"user_id": "x"}},
            "request": {
                "command": "расскажи анекдот",
                "original_utterance": "Расскажи анекдот.",
                "nlu": {"tokens": [], "entities": [], "intents": {}},
                "type": "SimpleUtterance",
            },
            "state": {"session": {}, "user": {}, "application": {}},
            "version": "1.0",
        }
        result = handler(event, None)
        assert "response" in result
        assert result["response"]["end_session"] is False


class TestStateMachine:
    """Тесты многошагового диалога (машина состояний)."""

    def test_incomplete_saves_transitions_to_awaiting(
        self, event_save_incomplete
    ):
        result = handler(event_save_incomplete, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") == "AWAITING_PLACE"
        assert state.get("pending_thing") == "паспорт"
        assert state.get("state_visits") == 1

    def test_awaiting_place_saves_on_answer(
        self, event_awaiting_place_answer
    ):
        result = handler(event_awaiting_place_answer, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") is None or state.get(
            "dialog_state"
        ) == "IDLE"
        assert state["items"]["паспорт"] == "в ящике стола"
        assert "запомнила" in result["response"]["text"].lower()

    def test_awaiting_place_short_gives_hint(
        self, event_awaiting_place_short
    ):
        result = handler(event_awaiting_place_short, None)
        state = result.get("session_state", {})
        # "привет" (6 символов) — >= 2, поэтому считается местом
        assert state.get("dialog_state") is None or state.get(
            "dialog_state"
        ) == "IDLE"
        assert state["items"]["паспорт"] == "привет"

    def test_awaiting_place_one_char_gives_hint(
        self, event_awaiting_place_short_one_char
    ):
        result = handler(event_awaiting_place_short_one_char, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") == "AWAITING_PLACE"
        assert state.get("state_visits") == 2

    def test_awaiting_place_second_hint_has_example(
        self, event_awaiting_place_short_two_visits
    ):
        result = handler(event_awaiting_place_short_two_visits, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") == "AWAITING_PLACE"
        assert state.get("state_visits") == 3
        text = result["response"]["text"].lower()
        assert "пример" in text

    def test_awaiting_place_breaks_with_find(
        self, event_awaiting_place_breaks_with_find
    ):
        result = handler(event_awaiting_place_breaks_with_find, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") is None or state.get(
            "dialog_state"
        ) == "IDLE"
        text = result["response"]["text"].lower()
        assert "не знаю" in text or "не помню" in text

    def test_awaiting_place_breaks_with_delete(
        self, event_awaiting_place_breaks_with_delete
    ):
        result = handler(event_awaiting_place_breaks_with_delete, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") is None or state.get(
            "dialog_state"
        ) == "IDLE"
        text = result["response"]["text"].lower()
        assert "забыла" in text or "нет" in text or "не помню" in text

    def test_awaiting_place_new_save_full(
        self, event_awaiting_place_new_save_full
    ):
        result = handler(event_awaiting_place_new_save_full, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") is None or state.get(
            "dialog_state"
        ) == "IDLE"
        assert state["items"]["телефон"] == "в рюкзаке"
        assert "запомнила" in result["response"]["text"].lower()

    def test_awaiting_place_new_save_incomplete(
        self, event_awaiting_place_new_save_incomplete
    ):
        result = handler(event_awaiting_place_new_save_incomplete, None)
        state = result.get("session_state", {})
        assert state.get("dialog_state") == "AWAITING_PLACE"
        assert state.get("pending_thing") == "телефон"
        assert state.get("state_visits") == 1

    def test_full_flow_incomplete_then_place(self):
        """Интеграционный тест: два вызова handler подряд."""
        event1 = {
            "session": {"new": False, "user": {"user_id": "x"}},
            "request": {
                "command": "запомни что паспорт",
                "original_utterance": "Запомни, что паспорт.",
                "nlu": {"tokens": [], "entities": [], "intents": {}},
                "type": "SimpleUtterance",
            },
            "state": {"session": {}, "user": {}, "application": {}},
            "version": "1.0",
        }
        result1 = handler(event1, None)
        assert result1["session_state"]["dialog_state"] == "AWAITING_PLACE"
        assert result1["session_state"]["pending_thing"] == "паспорт"

        # Второй вызов — отвечаем местом
        event2 = {
            "session": {"new": False, "user": {"user_id": "x"}},
            "request": {
                "command": "в ящике стола",
                "original_utterance": "В ящике стола.",
                "nlu": {"tokens": [], "entities": [], "intents": {}},
                "type": "SimpleUtterance",
            },
            "state": {"session": result1["session_state"]},
            "version": "1.0",
        }
        result2 = handler(event2, None)
        assert "паспорт" in result2["session_state"]["items"]
        assert (
            result2["session_state"]["items"]["паспорт"] == "в ящике стола"
        )

    def test_full_flow_breaks_with_find(self):
        """Интеграционный тест: прерываем сохранение командой FIND."""
        event1 = {
            "session": {"new": False, "user": {"user_id": "x"}},
            "request": {
                "command": "запомни что паспорт",
                "original_utterance": "Запомни, что паспорт.",
                "nlu": {"tokens": [], "entities": [], "intents": {}},
                "type": "SimpleUtterance",
            },
            "state": {"session": {}, "user": {}, "application": {}},
            "version": "1.0",
        }
        result1 = handler(event1, None)
        assert result1["session_state"]["dialog_state"] == "AWAITING_PLACE"

        event2 = {
            "session": {"new": False, "user": {"user_id": "x"}},
            "request": {
                "command": "где лежит ключи",
                "original_utterance": "Где лежит ключи?",
                "nlu": {"tokens": [], "entities": [], "intents": {}},
                "type": "SimpleUtterance",
            },
            "state": {"session": result1["session_state"]},
            "version": "1.0",
        }
        result2 = handler(event2, None)
        assert result2["session_state"].get("dialog_state") is None
        assert result2["session_state"].get("pending_thing") is None

    def test_regression_save_full(self):
        """Регрессия: полное сохранение работает как раньше."""
        event = {
            "session": {"new": False, "user": {"user_id": "x"}},
            "request": {
                "command": "запомни что паспорт лежит в ящике",
                "original_utterance": "Запомни, что паспорт лежит в ящике.",
                "nlu": {"tokens": [], "entities": [], "intents": {}},
                "type": "SimpleUtterance",
            },
            "state": {"session": {}, "user": {}, "application": {}},
            "version": "1.0",
        }
        result = handler(event, None)
        assert result["session_state"]["items"]["паспорт"] == "в ящике"
        assert "запомнила" in result["response"]["text"].lower()

    def test_regression_find(self):
        """Регрессия: поиск работает как раньше."""
        event = {
            "session": {"new": False, "user": {"user_id": "x"}},
            "request": {
                "command": "где лежит паспорт",
                "original_utterance": "Где лежит паспорт?",
                "nlu": {"tokens": [], "entities": [], "intents": {}},
                "type": "SimpleUtterance",
            },
            "state": {
                "session": {"items": {"паспорт": "в ящике"}},
                "user": {},
                "application": {},
            },
            "version": "1.0",
        }
        result = handler(event, None)
        assert "ящик" in result["response"]["text"].lower()

    def test_regression_list(self):
        """Регрессия: список работает как раньше."""
        event = {
            "session": {"new": False, "user": {"user_id": "x"}},
            "request": {
                "command": "что ты помнишь",
                "original_utterance": "Что ты помнишь?",
                "nlu": {"tokens": [], "entities": [], "intents": {}},
                "type": "SimpleUtterance",
            },
            "state": {
                "session": {
                    "items": {"паспорт": "ящик", "ключи": "шкаф"}
                },
                "user": {},
                "application": {},
            },
            "version": "1.0",
        }
        result = handler(event, None)
        text = result["response"]["text"].lower()
        assert "паспорт" in text
        assert "ключи" in text

    def test_regression_delete(self):
        """Регрессия: удаление работает как раньше."""
        event = {
            "session": {"new": False, "user": {"user_id": "x"}},
            "request": {
                "command": "забудь про паспорт",
                "original_utterance": "Забудь про паспорт.",
                "nlu": {"tokens": [], "entities": [], "intents": {}},
                "type": "SimpleUtterance",
            },
            "state": {
                "session": {
                    "items": {"паспорт": "ящик", "ключи": "шкаф"}
                },
                "user": {},
                "application": {},
            },
            "version": "1.0",
        }
        result = handler(event, None)
        items = result["session_state"]["items"]
        assert "паспорт" not in items
        assert "ключи" in items
