from __future__ import annotations

import logging

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

    def test_empty_string_returns_no_head(self):
        """Empty string returns NO_HEAD with empty canonical_key (degraded)."""
        result = normalize_thing("")
        assert result.status == DecomposeStatus.NO_HEAD
        assert result.canonical_key == ""
        assert result.display_name == ""


# ── Logging tests ─────────────────────────────────────────────────────────────


class TestNormalizeLogging:
    """Tests for normalize_thing logging."""

    def test_ok_logs_info(self, caplog):
        """normalize_thing logs INFO on successful decomposition."""
        with caplog.at_level(logging.INFO, logger="src.nlu.thing.normalize"):
            normalize_thing("смартфон")
        assert any("normalize OK" in record.message for record in caplog.records)

    def test_no_head_logs_warning(self, caplog):
        """normalize_thing logs WARNING on NO_HEAD status."""
        with caplog.at_level(logging.WARNING, logger="src.nlu.thing.normalize"):
            normalize_thing("прекрасно")
        assert any("NO_HEAD" in record.message for record in caplog.records)

    def test_ambiguous_head_logs_warning(self, caplog):
        """normalize_thing logs WARNING on AMBIGUOUS_HEAD status."""
        with caplog.at_level(logging.WARNING, logger="src.nlu.thing.normalize"):
            normalize_thing("мама мыла раму")
        assert any("AMBIGUOUS_HEAD" in record.message for record in caplog.records)

    def test_ok_logs_raw_input(self, caplog):
        """normalize_thing logs the raw input on OK."""
        with caplog.at_level(logging.INFO, logger="src.nlu.thing.normalize"):
            normalize_thing("мобильник")
        assert any("raw=мобильник" in record.message for record in caplog.records)
