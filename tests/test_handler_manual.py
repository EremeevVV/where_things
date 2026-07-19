"""Ручной запуск сценариев.

Запуск:
    uv run --no-sync python tests/test_handler_manual.py
    uv run --no-sync python tests/test_handler_manual.py launch
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from aliceio.fsm.context import FSMContext  # noqa: E402
from aliceio.fsm.storage.base import StorageKey  # noqa: E402
from aliceio.fsm.storage.memory import MemoryStorage  # noqa: E402
from aliceio.types import NLU, Application, Message, Session, User  # noqa: E402

from src.handlers import (  # noqa: E402
    handle_delete,
    handle_find,
    handle_launch,
    handle_list,
    handle_save,
)
from src.memory_repository import InMemoryItemsRepository  # noqa: E402

TEST_DATA = Path(__file__).resolve().parent.parent / "test_data"
_REPO = InMemoryItemsRepository()
_STORAGE = MemoryStorage()


def load_event(name: str) -> dict:
    """Load test event from JSON file."""
    return json.loads((TEST_DATA / f"{name}.json").read_text(encoding="utf-8"))


def _event_to_message(event: dict) -> Message:
    session_data = event.get("session", {})
    request = event.get("request", {})
    nlu_data = request.get("nlu", {})

    user_data = session_data.get("user")
    has_user = user_data and user_data.get("user_id")
    user = User(user_id=user_data["user_id"]) if has_user else None
    app_id = session_data.get("application", {}).get("application_id", "test")
    app = Application(application_id=app_id)
    session = Session(
        message_id=session_data.get("message_id", 1),
        session_id=session_data.get("session_id", "test"),
        skill_id=session_data.get("skill_id", "test"),
        application=app,
        new=session_data.get("new", False),
        user=user,
    )
    nlu = NLU(
        tokens=nlu_data.get("tokens", []),
        entities=nlu_data.get("entities", []),
        intents=nlu_data.get("intents", {}),
    )
    return Message(
        session=session,
        type=request.get("type", "SimpleUtterance"),
        command=request.get("command", ""),
        original_utterance=request.get("original_utterance", ""),
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


SCENARIOS: dict[str, Any] = {
    "launch": handle_launch,
    "save_item": lambda m: handle_save(m, _make_fsm(), _REPO),
    "save_multiword": lambda m: handle_save(m, _make_fsm(), _REPO),
    "save_incomplete": lambda m: handle_save(m, _make_fsm(), _REPO),
    "find_item": lambda m: handle_find(m, _REPO),
    "find_unknown": lambda m: handle_find(m, _REPO),
    "list_items": lambda m: handle_list(m, _REPO),
    "delete_item": lambda m: handle_delete(m, _REPO),
}


def run_all() -> None:
    """Run all test scenarios."""
    for name in SCENARIOS:
        run_one(name)


def run_one(name: str) -> None:
    """Run a single test scenario."""
    handler_fn = SCENARIOS.get(name)
    if handler_fn is None:
        print(f"Unknown: {name}")
        print(f"Available: {', '.join(SCENARIOS)}")
        return
    event = load_event(name)
    msg = _event_to_message(event)
    result = asyncio.run(handler_fn(msg))
    print(json.dumps({"text": result.response.text}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_one(sys.argv[1])
    else:
        run_all()
