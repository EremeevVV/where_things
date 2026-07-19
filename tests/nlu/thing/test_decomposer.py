from __future__ import annotations

from src.nlu.thing.decomposer import DecomposeStatus, decompose


class TestDecomposeBasic:
    """Базовые тесты разбора именных групп."""

    def test_single_noun(self):
        """Одиночное существительное -> head без модификаторов."""
        result = decompose("ключ")
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert result.descriptor.detected_head == "ключ"
        assert result.descriptor.adj_modifiers == ()
        assert result.descriptor.noun_modifiers == ()

    def test_noun_with_adj(self):
        """Существительное с прилагательным."""
        result = decompose("гаечный ключ")
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert result.descriptor.detected_head == "ключ"
        assert result.descriptor.adj_modifiers == ("гаечный",)
        assert result.descriptor.noun_modifiers == ()

    def test_noun_with_noun_preposition(self):
        """Существительное с предложным дополнением."""
        result = decompose("ключи от машины")
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert result.descriptor.detected_head == "ключ"
        assert result.descriptor.noun_modifiers == ("машина",)

    def test_complex_phrase(self):
        """Сложная фраза с прилагательным и предложным дополнением."""
        result = decompose("запасной ключ от машины")
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert result.descriptor.detected_head == "ключ"
        assert "машина" in result.descriptor.noun_modifiers

    def test_multiple_adjectives(self):
        """Несколько прилагательных."""
        result = decompose("мой старый ключ")
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert result.descriptor.detected_head == "ключ"
        assert len(result.descriptor.adj_modifiers) >= 1


class TestDecomposeOrderIndependence:
    """Порядок слов не должен влиять на результат."""

    def test_head_at_end(self):
        """Головное слово в конце фразы."""
        result = decompose("от машины ключ")
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert result.descriptor.detected_head == "ключ"

    def test_head_at_start(self):
        """Головное слово в начале фразы."""
        result = decompose("ключ от машины")
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert result.descriptor.detected_head == "ключ"


class TestDecomposeDeclension:
    """Падежные формы не должны ломать разбор."""

    def test_accusative_case(self):
        """Винительный падеж head (имитация слота после 'запомни')."""
        result = decompose("зарядку")
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert result.descriptor.detected_head == "зарядка"

    def test_genitive_singular(self):
        """Родительный падеж единственного числа."""
        result = decompose("два ключа от машины")
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert result.descriptor.detected_head == "ключ"

    def test_adjective_declension(self):
        """Склонённое прилагательное."""
        result = decompose("зимняя резина")
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert result.descriptor.detected_head == "резина"
        assert result.descriptor.adj_modifiers == ("зимний",)


class TestDecomposeAmbiguity:
    """Неоднозначные случаи."""

    def test_two_nouns_no_head_clear(self):
        """Два существительных без явного главного -> AMBIGUOUS_HEAD."""
        result = decompose("телефон зарядка")
        assert result.status == DecomposeStatus.AMBIGUOUS_HEAD
        assert result.descriptor is None
        assert len(result.candidates) == 2

    def test_only_adjective(self):
        """Только прилагательное -> NO_HEAD (фактическое поведение)."""
        result = decompose("старый")
        assert result.status == DecomposeStatus.NO_HEAD
        assert result.descriptor is None


class TestDecomposeInvariants:
    """Инварианты, которые должны выполняться всегда."""

    def test_descriptor_fields_not_empty(self):
        """Descriptor существует -> display и detected_head не пустые."""
        result = decompose("гаечный ключ")
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert result.descriptor.display != ""
        assert result.descriptor.detected_head != ""

    def test_head_not_in_noun_modifiers(self):
        """detected_head не входит в noun_modifiers."""
        result = decompose("ключ от машины")
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert result.descriptor.detected_head not in result.descriptor.noun_modifiers

    def test_modifiers_sorted_no_duplicates(self):
        """adj_modifiers и noun_modifiers отсортированы, без дублей."""
        result = decompose("запасной ключ от машины")
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert list(result.descriptor.adj_modifiers) == sorted(result.descriptor.adj_modifiers)
        assert list(result.descriptor.noun_modifiers) == sorted(result.descriptor.noun_modifiers)
        assert len(result.descriptor.adj_modifiers) == len(set(result.descriptor.adj_modifiers))
        assert len(result.descriptor.noun_modifiers) == len(set(result.descriptor.noun_modifiers))

    def test_display_preserves_original(self):
        """Display сохраняет оригинальную фразу."""
        phrase = "гаечный ключ от машины"
        result = decompose(phrase)
        assert result.status == DecomposeStatus.OK
        assert result.descriptor is not None
        assert result.descriptor.display == phrase
