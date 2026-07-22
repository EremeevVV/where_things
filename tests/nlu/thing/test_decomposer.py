from __future__ import annotations

from src.nlu.thing.decomposer import (
    DecomposeResult,
    DecomposeStatus,
    Reason,
    ResolvedToken,
    _total,
    decompose,
    score_genitive_demotion,
    score_unique_noun,
)

TEST_KEY = "ключ"


def _assert_ok_head(actual: DecomposeResult, expected_head: str) -> None:
    """Проверить успешный разбор с указанным головным словом."""
    assert actual.status == DecomposeStatus.OK
    assert actual.descriptor is not None
    assert actual.descriptor.detected_head == expected_head


class TestDecomposeBasic:
    """Базовые тесты разбора именных групп."""

    def test_single_noun(self):
        """Одиночное существительное -> head без модификаторов."""
        actual = decompose(TEST_KEY)
        _assert_ok_head(actual, TEST_KEY)
        assert actual.descriptor.adj_modifiers == ()
        assert actual.descriptor.noun_modifiers == ()

    def test_noun_with_adj(self):
        """Существительное с прилагательным."""
        actual = decompose("гаечный ключ")
        _assert_ok_head(actual, TEST_KEY)
        assert actual.descriptor.adj_modifiers == ("гаечный",)
        assert actual.descriptor.noun_modifiers == ()

    def test_noun_with_ambiguous_adj(self):
        """Существительное с прилагательным, которое иногда существительное."""
        actual = decompose("рабочий ноутбук")
        _assert_ok_head(actual, "ноутбук")
        assert actual.descriptor.adj_modifiers == ("рабочий",)
        assert actual.descriptor.noun_modifiers == ()

    def test_noun_with_noun_preposition(self):
        """Существительное с предложным дополнением."""
        actual = decompose("ключи от машины")
        _assert_ok_head(actual, TEST_KEY)
        assert actual.descriptor.noun_modifiers == ("машина",)

    def test_complex_phrase(self):
        """Сложная фраза с прилагательным и предложным дополнением."""
        actual = decompose("запасной ключ от машины")
        _assert_ok_head(actual, TEST_KEY)
        assert "машина" in actual.descriptor.noun_modifiers

    def test_multiple_adjectives(self):
        """Несколько прилагательных."""
        actual = decompose("мой старый ключ")
        _assert_ok_head(actual, TEST_KEY)
        assert len(actual.descriptor.adj_modifiers) >= 1


class TestDecomposeOrderIndependence:
    """Порядок слов не должен влиять на результат."""

    def test_head_at_end(self):
        """Головное слово в конце фразы."""
        actual = decompose("от машины ключ")
        _assert_ok_head(actual, TEST_KEY)

    def test_head_at_start(self):
        """Головное слово в начале фразы."""
        actual = decompose("ключ от машины")
        _assert_ok_head(actual, TEST_KEY)


class TestDecomposeDeclension:
    """Падежные формы не должны ломать разбор."""

    def test_accusative_case(self):
        """Винительный падеж head (имитация слота после 'запомни')."""
        actual = decompose("зарядку")
        assert actual.status == DecomposeStatus.OK
        assert actual.descriptor is not None
        assert actual.descriptor.detected_head == "зарядка"

    def test_genitive_singular(self):
        """Родительный падеж единственного числа."""
        actual = decompose("два ключа от машины")
        _assert_ok_head(actual, TEST_KEY)

    def test_adjective_declension(self):
        """Склонённое прилагательное."""
        actual = decompose("зимняя резина")
        assert actual.status == DecomposeStatus.OK
        assert actual.descriptor is not None
        assert actual.descriptor.detected_head == "резина"
        assert actual.descriptor.adj_modifiers == ("зимний",)


class TestDecomposeAmbiguity:
    """Неоднозначные случаи."""

    def test_two_nouns_no_head_clear(self):
        """Два существительных без явного главного -> AMBIGUOUS_HEAD."""
        actual = decompose("телефон зарядка")
        assert actual.status == DecomposeStatus.AMBIGUOUS_HEAD
        assert actual.descriptor is None
        assert len(actual.candidates) == 2

    def test_only_adjective(self):
        """Только прилагательное -> NO_HEAD (фактическое поведение)."""
        actual = decompose("старый")
        assert actual.status == DecomposeStatus.NO_HEAD
        assert actual.descriptor is None


class TestDecomposeInvariants:
    """Инварианты, которые должны выполняться всегда."""

    def test_descriptor_fields_not_empty(self):
        """Descriptor существует -> display и detected_head не пустые."""
        actual = decompose("гаечный ключ")
        _assert_ok_head(actual, TEST_KEY)
        assert actual.descriptor.display != ""

    def test_head_not_in_noun_modifiers(self):
        """detected_head не входит в noun_modifiers."""
        actual = decompose("ключ от машины")
        _assert_ok_head(actual, TEST_KEY)
        assert actual.descriptor.detected_head not in actual.descriptor.noun_modifiers

    def test_modifiers_sorted_no_duplicates(self):
        """adj_modifiers и noun_modifiers отсортированы, без дублей."""
        actual = decompose("запасной ключ от машины")
        _assert_ok_head(actual, TEST_KEY)
        assert list(actual.descriptor.adj_modifiers) == sorted(actual.descriptor.adj_modifiers)
        assert list(actual.descriptor.noun_modifiers) == sorted(actual.descriptor.noun_modifiers)
        assert len(actual.descriptor.adj_modifiers) == len(set(actual.descriptor.adj_modifiers))
        assert len(actual.descriptor.noun_modifiers) == len(set(actual.descriptor.noun_modifiers))

    def test_display_preserves_original(self):
        """Display сохраняет оригинальную фразу."""
        phrase = "гаечный ключ от машины"
        actual = decompose(phrase)
        _assert_ok_head(actual, TEST_KEY)
        assert actual.descriptor.display == phrase


# ── POS resolution (Etapa 2a) ────────────────────────────────────────────────


class TestPosResolution:
    """Тесты разрешения омонимии NOUN vs ADJ."""

    def test_ambiguous_adj_resolved_to_adj_before_noun(self):
        """рабочий ноутбук: 'рабочий' resolves to ADJ (agrees with ноутбук)."""
        actual = decompose("рабочий ноутбук")
        _assert_ok_head(actual, "ноутбук")
        assert actual.descriptor.adj_modifiers == ("рабочий",)
        assert actual.descriptor.noun_modifiers == ()

    def test_ambiguous_adj_resolved_to_adj_military(self):
        """военный билет: 'военный' resolves to ADJ (agrees with билет)."""
        actual = decompose("военный билет")
        _assert_ok_head(actual, "билет")
        assert actual.descriptor.adj_modifiers == ("военный",)
        assert actual.descriptor.noun_modifiers == ()

    def test_preposition_not_classified_as_modifier(self):
        """Предложения не попадают в модификаторы."""
        actual = decompose("зарядка для айфона")
        _assert_ok_head(actual, "зарядка")
        assert actual.descriptor.noun_modifiers == ("айфон",)
        # 'для' should NOT be in adj_modifiers
        assert "для" not in actual.descriptor.adj_modifiers

    def test_single_noun_only(self):
        """Одиночное существительное без модификаторов."""
        actual = decompose("телефон")
        _assert_ok_head(actual, "телефон")
        assert actual.descriptor.adj_modifiers == ()
        assert actual.descriptor.noun_modifiers == ()


# ── Scoring rules unit tests (Etapa 4) ──────────────────────────────────────


class TestScoringRules:
    """Unit-тесты правил скоринга."""

    def test_score_unique_noun_single(self):
        """score_unique_noun: +5 если один NOUN."""
        candidate = ResolvedToken(text="ключ", normal_form="ключ", is_noun=True, is_adj=False, case="nomn")
        all_nouns = (candidate,)
        result = score_unique_noun(candidate, all_nouns)
        assert result is not None
        assert result.reason == Reason.UNIQUE_NOUN
        assert result.points == 5

    def test_score_unique_noun_multiple(self):
        """score_unique_noun: None если больше одного NOUN."""
        n1 = ResolvedToken(text="ключ", normal_form="ключ", is_noun=True, is_adj=False, case="nomn")
        n2 = ResolvedToken(text="зарядка", normal_form="зарядка", is_noun=True, is_adj=False, case="nomn")
        result = score_unique_noun(n1, (n1, n2))
        assert result is None

    def test_score_genitive_demotion_gent(self):
        """score_genitive_demotion: -3 для genitive."""
        candidate = ResolvedToken(text="машины", normal_form="машина", is_noun=True, is_adj=False, case="gent")
        result = score_genitive_demotion(candidate, ())
        assert result is not None
        assert result.reason == Reason.GENITIVE_DEMOTED
        assert result.points == -3

    def test_score_genitive_demotion_non_gent(self):
        """score_genitive_demotion: None для non-genitive."""
        candidate = ResolvedToken(text="ключ", normal_form="ключ", is_noun=True, is_adj=False, case="nomn")
        result = score_genitive_demotion(candidate, ())
        assert result is None

    def test_total_scoring(self):
        """_total суммирует очки по правилам."""
        # Single noun: UNIQUE_NOUN(+5) + FIRST_AMONG_GENITIVE(0, not all gent) = 5
        n = ResolvedToken(text="ключ", normal_form="ключ", is_noun=True, is_adj=False, case="nomn", position=0)
        assert _total(n, (n,)) == 5

    def test_total_scoring_two_nouns(self):
        """_total: два nominative → равные очки."""
        n1 = ResolvedToken(text="телефон", normal_form="телефон", is_noun=True, is_adj=False, case="nomn", position=0)
        n2 = ResolvedToken(text="зарядка", normal_form="зарядка", is_noun=True, is_adj=False, case="nomn", position=1)
        assert _total(n1, (n1, n2)) == _total(n2, (n1, n2))

    def test_total_scoring_genitive_demoted(self):
        """_total: genitive получает -3."""
        n1 = ResolvedToken(text="ключ", normal_form="ключ", is_noun=True, is_adj=False, case="nomn", position=0)
        n2 = ResolvedToken(text="машины", normal_form="машина", is_noun=True, is_adj=False, case="gent", position=2)
        assert _total(n1, (n1, n2)) > _total(n2, (n1, n2))
