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
        intent, slots = parse_intent("запомни что зарядка лежит на полке у окна")
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
        assert result.get("session_state", {}).get("items", {}).get("паспорт") is None


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
