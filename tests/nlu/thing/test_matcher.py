from __future__ import annotations

from src.nlu.thing.canonical_dict import CANONICAL_DICT
from src.nlu.thing.canonicalizer import CanonicalThing, canonicalize
from src.nlu.thing.decomposer import decompose
from src.nlu.thing.matcher import canonical_key, match

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


class TestMatchExact:
    """Тесты точного совпадения."""

    def test_exact_match(self):
        """Точное совпадение canonical_key -> exact."""
        query = _make_thing(TEST_KEY)
        candidate = _make_thing(TEST_KEY)
        actual = match(query, [candidate])
        assert actual.status == "exact"
        assert len(actual.matches) == 1

    def test_exact_match_with_modifiers(self):
        """Точное совпадение с модификаторами."""
        query = _make_thing(TEST_WRENCH)
        candidate = _make_thing(TEST_WRENCH)
        actual = match(query, [candidate])
        assert actual.status == "exact"


class TestMatchAmbiguous:
    """Тесты неоднозначных результатов."""

    def test_ambiguous_head_candidates(self):
        """Ключ при кандидатах с одинаковым head -> ambiguous."""
        query = _make_thing(TEST_KEY)
        wrench = _make_thing(TEST_WRENCH)
        cupboard = _make_thing("амбарный ключ")
        actual = match(query, [wrench, cupboard])
        assert actual.status in ("ambiguous", "ranked")
        assert len(actual.matches) >= 1


class TestMatchEmpty:
    """Тесты без результатов."""

    def test_no_match_different_head(self):
        """Запрос без совпадений по head -> empty."""
        query = _make_thing(TEST_KEY)
        charger = _make_thing("зарядка")
        actual = match(query, [charger])
        assert actual.status == "empty"
        assert len(actual.matches) == 0

    def test_empty_candidates(self):
        """Пустой список кандидатов -> empty."""
        query = _make_thing(TEST_KEY)
        actual = match(query, [])
        assert actual.status == "empty"
