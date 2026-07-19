import json
from pathlib import Path

import pytest

TEST_DATA = Path(__file__).resolve().parent.parent / "test_data"


def load_event(name: str) -> dict:
    """Load test event from JSON file."""
    return json.loads((TEST_DATA / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def event_launch():
    """Launch event fixture."""
    return load_event("launch")


@pytest.fixture
def event_save():
    """Save item event fixture."""
    return load_event("save_item")


@pytest.fixture
def event_save_multiword():
    """Save multiword item event fixture."""
    return load_event("save_multiword")


@pytest.fixture
def event_save_incomplete():
    """Save incomplete event fixture."""
    return load_event("save_incomplete")


@pytest.fixture
def event_find():
    """Find item event fixture."""
    return load_event("find_item")


@pytest.fixture
def event_find_unknown():
    """Find unknown item event fixture."""
    return load_event("find_unknown")


@pytest.fixture
def event_list():
    """List items event fixture."""
    return load_event("list_items")


@pytest.fixture
def event_delete():
    """Delete item event fixture."""
    return load_event("delete_item")


@pytest.fixture
def event_awaiting_place_answer():
    """Awaiting place answer event fixture."""
    return load_event("awaiting_place_answer")


@pytest.fixture
def event_awaiting_place_short():
    """Awaiting place short event fixture."""
    return load_event("awaiting_place_short")


@pytest.fixture
def event_awaiting_place_short_one_char():
    """Awaiting place short one char event fixture."""
    return load_event("awaiting_place_short_one_char")


@pytest.fixture
def event_awaiting_place_short_two_visits():
    """Awaiting place short two visits event fixture."""
    return load_event("awaiting_place_short_two_visits")


@pytest.fixture
def event_awaiting_place_breaks_with_find():
    """Awaiting place breaks with find event fixture."""
    return load_event("awaiting_place_breaks_with_find")


@pytest.fixture
def event_awaiting_place_breaks_with_delete():
    """Awaiting place breaks with delete event fixture."""
    return load_event("awaiting_place_breaks_with_delete")


@pytest.fixture
def event_awaiting_place_new_save_full():
    """Awaiting place new save full event fixture."""
    return load_event("awaiting_place_new_save_full")


@pytest.fixture
def event_awaiting_place_new_save_incomplete():
    """Awaiting place new save incomplete event fixture."""
    return load_event("awaiting_place_new_save_incomplete")
