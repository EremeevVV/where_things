from __future__ import annotations

from src.nlu.thing.canonical_dict import CANONICAL_DICT
from src.nlu.thing.canonicalizer import CanonicalThing, canonicalize
from src.nlu.thing.decomposer import decompose
from src.nlu.thing.matcher import canonical_key

TEST_KEY = "ключ"
TEST_WRENCH = "гаечный ключ"


def _make_thing(phrase: str) -> CanonicalThing:
    """Хелпер: разобрать фразу и канонизировать."""
    actual = decompose(phrase)
    assert actual.descriptor is not None
    return canonicalize(actual.descriptor, CANONICAL_DICT)


class TestCanonicalKey:
    """Тесты ключа идентичности."""

    def test_simple_key(self):
        """Простой ключ для одиночного существительного."""
        thing = _make_thing(TEST_KEY)
        key = canonical_key(thing)
        assert key == f"{TEST_KEY}#"

    def test_key_with_modifiers(self):
        """Ключ с модификаторами."""
        thing = _make_thing(TEST_WRENCH)
        key = canonical_key(thing)
        assert TEST_KEY in key
        assert "гаечный" in key

    def test_key_sorted_modifiers(self):
        """Модификаторы в ключе отсортированы."""
        thing = _make_thing("запасной ключ от машины")
        key = canonical_key(thing)
        parts = key.split("#")
        assert len(parts) == 2
        mods = parts[1].split(",") if parts[1] else []
        assert mods == sorted(mods)
