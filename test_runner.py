"""
Симуляция Yandex Cloud Functions окружения для локального тестирования.

Запуск:
    uv run python test_runner.py              # все сценарии
    uv run python test_runner.py launch       # один сценарий
    uv run python test_runner.py save find    # несколько сценариев
"""
import json
import sys
import time
from pathlib import Path

from main import handler

TEST_DATA = Path("test_data")


def load_event(name: str) -> dict:
    path = TEST_DATA / f"{name}.json"
    if not path.exists():
        available = [f.stem for f in TEST_DATA.glob("*.json")]
        print(f"Unknown event: {name}")
        print(f"Available: {', '.join(available)}")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def run_scenario(name: str) -> dict:
    event = load_event(name)
    start = time.perf_counter()
    result = handler(event, None)
    elapsed_ms = (time.perf_counter() - start) * 1000

    response = result.get("response", {})
    text = response.get("text", "")
    end_session = response.get("end_session", None)

    print(f"\n{'=' * 50}")
    print(f"  Scenario: {name}")
    print(f"{'=' * 50}")
    print(f"  Request command : {event.get('request', {}).get('command', '(empty)')}")
    print(f"  Response text   : {text}")
    print(f"  End session     : {end_session}")
    print(f"  Time            : {elapsed_ms:.1f}ms")

    warnings = []
    if elapsed_ms > 4500:
        warnings.append(f"SLOW: {elapsed_ms:.0f}ms > 4500ms limit")
    if len(text) > 5000:
        warnings.append(f"TEXT TOO LONG: {len(text)} chars > 5000 limit")
    if "response" not in result:
        warnings.append("MISSING 'response' key")
    if "version" not in result:
        warnings.append("MISSING 'version' key")
    if end_session is None:
        warnings.append("MISSING 'end_session'")

    if warnings:
        for w in warnings:
            print(f"  WARNING: {w}")
    else:
        print("  Status: OK")

    return result


def main():
    scenarios = sys.argv[1:] if len(sys.argv) > 1 else [
        "launch", "save_item", "find_item", "list_items", "delete_item"
    ]

    print("Yandex Cloud Functions local simulator")
    print(f"Running {len(scenarios)} scenario(s)...\n")

    results = {}
    for name in scenarios:
        results[name] = run_scenario(name)

    print(f"\n{'=' * 50}")
    print(f"  Summary: {len(results)} scenarios executed")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
