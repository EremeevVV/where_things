"""
Симуляция Yandex Cloud Functions для локального тестирования.

Запуск:
    uv run --no-sync python tests/test_runner.py
    uv run --no-sync python tests/test_runner.py launch
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from aliceio.types import NLU, Application, Message, Session, User  # noqa: E402

from src.handlers import (  # noqa: E402
    handle_delete,
    handle_find,
    handle_launch,
    handle_list,
    handle_save,
    handle_unknown,
)
from src.memory_repository import InMemoryItemsRepository  # noqa: E402

TEST_DATA = Path(__file__).resolve().parent.parent / "test_data"
_REPO = InMemoryItemsRepository()


def load_event(name: str) -> dict:
    path = TEST_DATA / f"{name}.json"
    if not path.exists():
        available = [f.stem for f in TEST_DATA.glob("*.json")]
        print(f"Unknown event: {name}")
        print(f"Available: {', '.join(available)}")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def _event_to_message(event: dict) -> Message:
    session_data = event.get("session", {})
    request = event.get("request", {})
    nlu_data = request.get("nlu", {})

    user_data = session_data.get("user")
    has_user = user_data and user_data.get("user_id")
    user = User(user_id=user_data["user_id"]) if has_user else None
    app_id = session_data.get("application", {}).get(
        "application_id", "test"
    )
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


def run_scenario(name: str) -> None:
    event = load_event(name)
    msg = _event_to_message(event)
    start = time.perf_counter()

    intents = msg.nlu.intents if msg.nlu else {}
    if msg.session.new:
        result = asyncio.run(handle_launch(msg))
    elif "save" in intents:
        result = asyncio.run(handle_save(msg, None, _REPO))
    elif "find" in intents:
        result = asyncio.run(handle_find(msg, _REPO))
    elif "list" in intents:
        result = asyncio.run(handle_list(msg, _REPO))
    elif "delete" in intents:
        result = asyncio.run(handle_delete(msg, _REPO))
    else:
        result = asyncio.run(handle_unknown(msg))

    elapsed_ms = (time.perf_counter() - start) * 1000
    text = result.response.text

    print(f"\n{'=' * 50}")
    print(f"  Scenario: {name}")
    print(f"{'=' * 50}")
    cmd = event.get("request", {}).get("command", "(empty)")
    print(f"  Request command : {cmd}")
    print(f"  Response text   : {text}")
    print(f"  Time            : {elapsed_ms:.1f}ms")

    warnings = []
    if elapsed_ms > 4500:
        warnings.append(f"SLOW: {elapsed_ms:.0f}ms > 4500ms limit")
    if len(text) > 5000:
        warnings.append(f"TEXT TOO LONG: {len(text)} > 5000")

    for w in warnings:
        print(f"  WARNING: {w}")
    if not warnings:
        print("  Status: OK")


def main() -> None:
    scenarios = sys.argv[1:] if len(sys.argv) > 1 else [
        "launch", "save_item", "find_item", "list_items", "delete_item"
    ]
    print("Yandex Cloud Functions local simulator")
    print(f"Running {len(scenarios)} scenario(s)...\n")
    for name in scenarios:
        run_scenario(name)
    print(f"\n{'=' * 50}")
    print(f"  Summary: {len(scenarios)} scenarios executed")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
