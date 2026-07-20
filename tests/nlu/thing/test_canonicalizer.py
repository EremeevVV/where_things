from __future__ import annotations

from src.nlu.thing.canonical_dict import CANONICAL_DICT
from src.nlu.thing.canonicalizer import canonicalize
from src.nlu.thing.decomposer import ThingDescriptor


class TestCanonicalizeBasic:
    """Базовые тесты канонизации."""

    def test_word_in_dict(self):
        """Слово в словаре заменяется на каноническое."""
        td = ThingDescriptor(
            display="смартфон",
            detected_head="смартфон",
            adj_modifiers=(),
            noun_modifiers=(),
        )
        actual = canonicalize(td, CANONICAL_DICT)
        assert actual.canonical_head == "телефон"

    def test_word_not_in_dict(self):
        """Слова вне словаря возвращаются без изменений."""
        td = ThingDescriptor(
            display="ключи",
            detected_head="ключ",
            adj_modifiers=(),
            noun_modifiers=(),
        )
        actual = canonicalize(td, CANONICAL_DICT)
        assert actual.canonical_head == "ключ"

    def test_noun_modifiers_canonicalized(self):
        """Именные модификаторы канонизируются поэлементно."""
        td = ThingDescriptor(
            display="зарядка для айфона",
            detected_head="зарядка",
            adj_modifiers=(),
            noun_modifiers=("айфон",),
        )
        actual = canonicalize(td, CANONICAL_DICT)
        assert actual.canonical_noun_modifiers == ("телефон",)

    def test_adj_modifiers_not_canonicalized(self):
        """Прилагательные не канонизируются (ADR)."""
        td = ThingDescriptor(
            display="зимняя резина",
            detected_head="резина",
            adj_modifiers=("зимний",),
            noun_modifiers=(),
        )
        actual = canonicalize(td, CANONICAL_DICT)
        assert actual.adj_modifiers == ("зимний",)


class TestCanonicalizeIdempotency:
    """Идемпотентность канонизации."""

    def test_idempotent_for_all_dict_values(self):
        """Canonicalize идемпотентен для всех значений словаря."""
        for canonical_form in CANONICAL_DICT.values():
            td = ThingDescriptor(
                display=canonical_form,
                detected_head=canonical_form,
                adj_modifiers=(),
                noun_modifiers=(),
            )
            first = canonicalize(td, CANONICAL_DICT)
            second = canonicalize(first, CANONICAL_DICT)
            assert first.canonical_head == second.canonical_head


class TestCanonicalizeRegression:
    """Регрессионные тесты."""

    def test_charge_for_iphone_and_phone_same(self):
        """Зарядка для айфона и телефона канонизируются одинаково."""
        td_iphone = ThingDescriptor(
            display="зарядка для айфона",
            detected_head="зарядка",
            adj_modifiers=(),
            noun_modifiers=("айфон",),
        )
        td_phone = ThingDescriptor(
            display="зарядка для телефона",
            detected_head="зарядка",
            adj_modifiers=(),
            noun_modifiers=("телефон",),
        )
        result_iphone = canonicalize(td_iphone, CANONICAL_DICT)
        result_phone = canonicalize(td_phone, CANONICAL_DICT)
        assert result_iphone.canonical_noun_modifiers == result_phone.canonical_noun_modifiers
