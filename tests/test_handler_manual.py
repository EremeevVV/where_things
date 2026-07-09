import json
from pathlib import Path

from main import handler

TEST_DATA = Path(__file__).resolve().parent.parent / "test_data"


def load_event(name: str) -> dict:
    return json.loads((TEST_DATA / f"{name}.json").read_text(encoding="utf-8"))


def run_all():
    scenarios = [
        "launch", "save_item", "save_multiword", "save_incomplete",
        "find_item", "find_unknown", "list_items", "delete_item",
    ]
    for name in scenarios:
        event = load_event(name)
        print(f"\n{'=' * 40}")
        print(f"  {name}")
        print(f"{'=' * 40}")
        result = handler(event, None)
        print(json.dumps(result, ensure_ascii=False, indent=2))


def run_one(name: str):
    event = load_event(name)
    result = handler(event, None)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        run_one(sys.argv[1])
    else:
        run_all()
