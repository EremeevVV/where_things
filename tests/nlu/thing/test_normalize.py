from __future__ import annotations

from src.nlu.thing.decomposer import DecomposeStatus
from src.nlu.thing.normalize import normalize_thing


class TestNormalizeOk:
    """Tests for normalize_thing with OK status."""

    def test_single_noun_canonicalized(self):
        """Single noun gets canonicalized via dict."""
        result = normalize_thing("смартфон")
        assert result.canonical_key == "телефон#"
        assert result.status == DecomposeStatus.OK

    def test_synonym_canonicalized(self):
        """Synonym gets same canonical key."""
        result = normalize_thing("мобильник")
        assert result.canonical_key == "телефон#"
        assert result.status == DecomposeStatus.OK

    def test_another_synonym(self):
        """Another synonym gets same canonical key."""
        result = normalize_thing("айфон")
        assert result.canonical_key == "телефон#"
        assert result.status == DecomposeStatus.OK

    def test_compound_phrase(self):
        """Compound phrase gets full canonical key."""
        result = normalize_thing("зарядка для айфона")
        assert "зарядка" in result.canonical_key
        assert result.status == DecomposeStatus.OK

    def test_display_name_is_raw(self):
        """display_name is always the original raw string."""
        result = normalize_thing("смартфон")
        assert result.display_name == "смартфон"

    def test_idempotent_for_head_without_modifiers(self):
        """Canonical head alone produces same key."""
        result = normalize_thing("телефон")
        assert result.canonical_key == "телефон#"


class TestNormalizeDegraded:
    """Tests for normalize_thing with degraded status."""

    def test_no_head(self):
        """Non-noun phrase gets NO_HEAD status and literal fallback."""
        result = normalize_thing("прекрасно")
        assert result.status == DecomposeStatus.NO_HEAD
        assert result.canonical_key == "прекрасно"
        assert result.display_name == "прекрасно"

    def test_ambiguous_head(self):
        """Ambiguous phrase gets AMBIGUOUS_HEAD and literal fallback."""
        result = normalize_thing("мама мыла раму")
        assert result.status == DecomposeStatus.AMBIGUOUS_HEAD
        assert result.canonical_key == "мама мыла раму"
        assert result.display_name == "мама мыла раму"

    def test_never_returns_none(self):
        """normalize_thing always returns a value."""
        result = normalize_thing("")
        assert result is not None
        assert isinstance(result.canonical_key, str)
