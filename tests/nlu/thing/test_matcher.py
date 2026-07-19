from __future__ import annotations

from src.nlu.thing.canonical_dict import CANONICAL_DICT
from src.nlu.thing.canonicalizer import CanonicalThing, canonicalize
from src.nlu.thing.decomposer import decompose
from src.nlu.thing.matcher import canonical_key, match


def _make_thing(phrase: str) -> CanonicalThing:
    """Хелпер: разобрать фразу и канонизировать."""
    result = decompose(phrase)
    assert result.descriptor is not None
    return canonicalize(result.descriptor, CANONICAL_DICT)


class TestCanonicalKey:
    """Тесты ключа идентичности."""

    def test_simple_key(self):
        """Простой ключ для одиночного существительного."""
        thing = _make_thing("ключ")
        key = canonical_key(thing)
        assert key == "ключ#"

    def test_key_with_modifiers(self):
        """Ключ с модификаторами."""
        thing = _make_thing("гаечный ключ")
        key = canonical_key(thing)
        assert "ключ" in key
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
        q = _make_thing("ключ")
        c = _make_thing("ключ")
        result = match(q, [c])
        assert result.status == "exact"
        assert len(result.matches) == 1

    def test_exact_match_with_modifiers(self):
        """Точное совпадение с модификаторами."""
        q = _make_thing("гаечный ключ")
        c = _make_thing("гаечный ключ")
        result = match(q, [c])
        assert result.status == "exact"


class TestMatchAmbiguous:
    """Тесты неоднозначных результатов."""

    def test_ambiguous_head_candidates(self):
        """Ключ при кандидатах с одинаковым head -> ambiguous."""
        q = _make_thing("ключ")
        c1 = _make_thing("гаечный ключ")
        c2 = _make_thing("амбарный ключ")
        result = match(q, [c1, c2])
        assert result.status in ("ambiguous", "ranked")
        assert len(result.matches) >= 1


class TestMatchEmpty:
    """Тесты без результатов."""

    def test_no_match_different_head(self):
        """Запрос без совпадений по head -> empty."""
        q = _make_thing("ключ")
        c = _make_thing("зарядка")
        result = match(q, [c])
        assert result.status == "empty"
        assert len(result.matches) == 0

    def test_empty_candidates(self):
        """Пустой список кандидатов -> empty."""
        q = _make_thing("ключ")
        result = match(q, [])
        assert result.status == "empty"
