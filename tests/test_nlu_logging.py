from __future__ import annotations

import logging

from aliceio.types import NLU, Application, Message, Session, User

from src.nlu.intents import DeleteIntent, FindIntent, SaveIntent


def _make_message(
    command: str,
    intents: dict | None = None,
) -> Message:
    """Create a Message with given intents."""
    user = User(user_id="test_user")
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


def _intents(name: str, slots: dict[str, str]) -> dict:
    """Build intents dict for a single intent with slots."""
    return {name: {"slots": {k: {"value": v} for k, v in slots.items()}}}


def _save_intents(
    thing: str,
    place: str,
    preposition: str = "",
    loc_verb: str = "",
) -> dict:
    """Build save intent with all 4 slots."""
    slots: dict[str, str] = {"thing": thing, "place": place}
    if preposition:
        slots["preposition"] = preposition
    if loc_verb:
        slots["loc_verb"] = loc_verb
    return _intents("save", slots)


# ── SaveIntent logging ────────────────────────────────────────────────────────


class TestSaveIntentLogging:
    """Tests for SaveIntent logging."""

    def test_save_intent_logs_thing(self, caplog):
        """SaveIntent.from_message logs the thing slot value."""
        intents = _save_intents("паспорт", "ящике", preposition="в", loc_verb="лежит")
        msg = _make_message("запомни что паспорт лежит в ящике", intents=intents)
        with caplog.at_level(logging.INFO, logger="src.nlu.intents"):
            SaveIntent.from_message(msg)
        assert any(
            "save intent parsed" in record.message and "thing=паспорт" in record.message for record in caplog.records
        )

    def test_save_intent_missing_thing_logs_warning(self, caplog):
        """SaveIntent.from_message logs WARNING when thing slot is missing."""
        intents = _intents("save", {"place": "ящике"})
        msg = _make_message("запомни что лежит в ящике", intents=intents)
        with caplog.at_level(logging.WARNING, logger="src.nlu.intents"):
            SaveIntent.from_message(msg)
        assert any("save intent missing thing slot" in record.message for record in caplog.records)


# ── FindIntent logging ────────────────────────────────────────────────────────


class TestFindIntentLogging:
    """Tests for FindIntent logging."""

    def test_find_intent_logs_thing(self, caplog):
        """FindIntent.from_message logs the thing slot value."""
        intents = _intents("find", {"thing": "паспорт"})
        msg = _make_message("где лежит паспорт", intents=intents)
        with caplog.at_level(logging.INFO, logger="src.nlu.intents"):
            FindIntent.from_message(msg)
        assert any(
            "find intent parsed" in record.message and "thing=паспорт" in record.message for record in caplog.records
        )

    def test_find_intent_missing_thing_logs_warning(self, caplog):
        """FindIntent.from_message logs WARNING when thing slot is missing."""
        intents = _intents("find", {})
        msg = _make_message("где лежит", intents=intents)
        with caplog.at_level(logging.WARNING, logger="src.nlu.intents"):
            FindIntent.from_message(msg)
        assert any("find intent missing thing slot" in record.message for record in caplog.records)


# ── DeleteIntent logging ──────────────────────────────────────────────────────


class TestDeleteIntentLogging:
    """Tests for DeleteIntent logging."""

    def test_delete_intent_logs_thing(self, caplog):
        """DeleteIntent.from_message logs the thing slot value."""
        intents = _intents("delete", {"thing": "паспорт"})
        msg = _make_message("забудь про паспорт", intents=intents)
        with caplog.at_level(logging.INFO, logger="src.nlu.intents"):
            DeleteIntent.from_message(msg)
        assert any(
            "delete intent parsed" in record.message and "thing=паспорт" in record.message for record in caplog.records
        )

    def test_delete_intent_missing_thing_logs_warning(self, caplog):
        """DeleteIntent.from_message logs WARNING when thing slot is missing."""
        intents = _intents("delete", {})
        msg = _make_message("забудь про", intents=intents)
        with caplog.at_level(logging.WARNING, logger="src.nlu.intents"):
            DeleteIntent.from_message(msg)
        assert any("delete intent missing thing slot" in record.message for record in caplog.records)
