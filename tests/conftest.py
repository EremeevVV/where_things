import json
from pathlib import Path

import pytest

TEST_DATA = Path(__file__).resolve().parent.parent / "test_data"


def load_event(name: str) -> dict:
    return json.loads((TEST_DATA / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def event_launch():
    return load_event("launch")


@pytest.fixture
def event_save():
    return load_event("save_item")


@pytest.fixture
def event_save_multiword():
    return load_event("save_multiword")


@pytest.fixture
def event_save_incomplete():
    return load_event("save_incomplete")


@pytest.fixture
def event_find():
    return load_event("find_item")


@pytest.fixture
def event_find_unknown():
    return load_event("find_unknown")


@pytest.fixture
def event_list():
    return load_event("list_items")


@pytest.fixture
def event_delete():
    return load_event("delete_item")


@pytest.fixture
def event_awaiting_place_answer():
    return load_event("awaiting_place_answer")


@pytest.fixture
def event_awaiting_place_short():
    return load_event("awaiting_place_short")


@pytest.fixture
def event_awaiting_place_short_one_char():
    return load_event("awaiting_place_short_one_char")


@pytest.fixture
def event_awaiting_place_short_two_visits():
    return load_event("awaiting_place_short_two_visits")


@pytest.fixture
def event_awaiting_place_breaks_with_find():
    return load_event("awaiting_place_breaks_with_find")


@pytest.fixture
def event_awaiting_place_breaks_with_delete():
    return load_event("awaiting_place_breaks_with_delete")


@pytest.fixture
def event_awaiting_place_new_save_full():
    return load_event("awaiting_place_new_save_full")


@pytest.fixture
def event_awaiting_place_new_save_incomplete():
    return load_event("awaiting_place_new_save_incomplete")
