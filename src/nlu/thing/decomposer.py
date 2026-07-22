from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import pymorphy3

logger = logging.getLogger(__name__)
morph = pymorphy3.MorphAnalyzer()


# ── Public API (unchanged) ───────────────────────────────────────────────────


class DecomposeStatus(StrEnum):
    """Статус результата разбора фразы."""

    OK = "ok"
    AMBIGUOUS_HEAD = "ambiguous_head"
    NO_HEAD = "no_head"


@dataclass(frozen=True)
class ThingDescriptor:
    """Результат разбора фразы. Всегда корректен, если существует."""

    display: str
    detected_head: str
    adj_modifiers: tuple[str, ...]
    noun_modifiers: tuple[str, ...]


@dataclass(frozen=True)
class DecomposeResult:
    """Обёртка над ThingDescriptor с диагностикой неоднозначности."""

    descriptor: ThingDescriptor | None
    status: DecomposeStatus
    candidates: tuple[str, ...] = ()


# ── Token-level structures (Etapa 1) ────────────────────────────────────────


@dataclass(frozen=True)
class TokenParses:
    """Все релевантные морфоразборы токена, без выбора победителя."""

    text: str
    noun_parse: Any  # pymorphy3.Parse or None
    adj_parse: Any  # pymorphy3.Parse or None


@dataclass(frozen=True)
class ResolvedToken:
    """Токен после POS-разрешения: NOUN, ADJ, или пропущен."""

    text: str
    normal_form: str
    is_noun: bool
    is_adj: bool
    case: str | None = None
    source: Any = None  # the winning Parse
    position: int = 0  # 0-based index in original phrase


# ── Scoring model (Etapa 3) ──────────────────────────────────────────────────


class Reason(StrEnum):
    """Именованная причина начисления очков."""

    UNIQUE_NOUN = "unique_noun"
    AGREES_WITH_NEIGHBOR_NOUN = "agrees_with_neighbor_noun"
    HAS_BOTH_NOUN_AND_ADJ_PARSE = "has_both_noun_and_adj_parse"
    GENITIVE_DEMOTED = "genitive_demoted"
    FIRST_AMONG_GENITIVE = "first_among_genitive"


@dataclass(frozen=True)
class ScoreDelta:
    """Один вклад в оценку кандидата."""

    reason: Reason
    points: int


_POINTS_UNIQUE_NOUN = 5
_POINTS_AGREEMENT = 2
_POINTS_GENITIVE_PENALTY = -3
_POINTS_FIRST_AMONG_GENITIVE = 1


# ── Token parsing (Etapa 1) ──────────────────────────────────────────────────


def _parse_tokens(thing_phrase: str) -> tuple[list[TokenParses], list[str]]:
    """Токенизация и морфоразбор: хранить все релевантные кандидаты."""
    tokens: list[TokenParses] = []
    raw_words: list[str] = []
    for token in thing_phrase.split():
        stripped = token.strip()
        noun = None
        adj = None
        for p in morph.parse(stripped):
            tag = p.tag
            if "NOUN" in tag and noun is None:
                noun = p
            elif ("ADJF" in tag or "PRTF" in tag) and adj is None:
                adj = p
        tokens.append(TokenParses(text=stripped, noun_parse=noun, adj_parse=adj))
        raw_words.append(stripped)
    return tokens, raw_words


# ── POS resolution (Etapa 2a) ────────────────────────────────────────────────


def _resolve_pos(tokens: list[TokenParses]) -> list[ResolvedToken]:
    """Разрешить POS для каждого токена. Для омонимов — скоринг."""
    resolved: list[ResolvedToken] = []
    for idx, tp in enumerate(tokens):
        has_noun = tp.noun_parse is not None
        has_adj = tp.adj_parse is not None

        if has_noun and not has_adj:
            resolved.append(_to_noun(tp, idx))
        elif has_adj and not has_noun:
            resolved.append(_to_adj(tp, idx))
        elif has_noun and has_adj:
            resolved.append(_resolve_ambiguous(tp, tokens, idx))
        else:
            # No parse at all — skip (prepositions, particles, etc.)
            resolved.append(ResolvedToken(text=tp.text, normal_form=tp.text, is_noun=False, is_adj=False, position=idx))
    return resolved


def _to_noun(tp: TokenParses, position: int = 0) -> ResolvedToken:
    """Convert TokenParses to ResolvedToken as NOUN."""
    p = tp.noun_parse
    return ResolvedToken(
        text=tp.text,
        normal_form=p.normal_form,
        is_noun=True,
        is_adj=False,
        case=p.tag.case,
        source=p,
        position=position,
    )


def _to_adj(tp: TokenParses, position: int = 0) -> ResolvedToken:
    """Convert TokenParses to ResolvedToken as ADJ."""
    p = tp.adj_parse
    return ResolvedToken(
        text=tp.text,
        normal_form=p.normal_form,
        is_noun=False,
        is_adj=True,
        source=p,
        position=position,
    )


def _resolve_ambiguous(tp: TokenParses, all_tokens: list[TokenParses], position: int) -> ResolvedToken:
    """Разрешить омонимию NOUN vs ADJ через согласование с соседями."""
    adj_p = tp.adj_parse

    # Check agreement: does this token agree with a neighboring NOUN?
    for neighbor in all_tokens:
        if neighbor is tp or neighbor.noun_parse is None:
            continue
        # Check if ADJ parse agrees with this neighbor noun in number/gender
        if _adj_agrees_with_noun(adj_p, neighbor.noun_parse):
            logger.debug(
                "POS resolved ADJ: token=%s agrees with neighbor=%s",
                tp.text,
                neighbor.text,
            )
            return _to_adj(tp, position)

    # Default: prefer NOUN (more useful as head candidate)
    logger.debug("POS resolved NOUN (default): token=%s", tp.text)
    return _to_noun(tp, position)


def _adj_agrees_with_noun(adj_parse: Any, noun_parse: Any) -> bool:
    """Проверить согласование прилагательного с существительным (число, род)."""
    adj_tag = adj_parse.tag
    noun_tag = noun_parse.tag
    return bool(adj_tag.number == noun_tag.number and adj_tag.gender == noun_tag.gender)


# ── Head selection rules (Etapa 4) ───────────────────────────────────────────


def score_unique_noun(
    candidate: ResolvedToken,
    all_nouns: tuple[ResolvedToken, ...],
) -> ScoreDelta | None:
    """+5, если candidate — единственный NOUN-токен в фразе."""
    if len(all_nouns) == 1:
        return ScoreDelta(reason=Reason.UNIQUE_NOUN, points=_POINTS_UNIQUE_NOUN)
    return None


def score_genitive_demotion(
    candidate: ResolvedToken,
    all_nouns: tuple[ResolvedToken, ...],
) -> ScoreDelta | None:
    """-3 для существительных в родительном падеже."""
    if candidate.case == "gent":
        return ScoreDelta(reason=Reason.GENITIVE_DEMOTED, points=_POINTS_GENITIVE_PENALTY)
    return None


def score_first_among_genitive(
    candidate: ResolvedToken,
    all_nouns: tuple[ResolvedToken, ...],
) -> ScoreDelta | None:
    """+1 если ВСЕ существительные в genitive — tiebreaker для «два ключа от машины»."""
    all_genitive = all(n.case == "gent" for n in all_nouns)
    if all_genitive:
        min_pos = min(n.position for n in all_nouns)
        if candidate.position == min_pos:
            return ScoreDelta(reason=Reason.FIRST_AMONG_GENITIVE, points=_POINTS_FIRST_AMONG_GENITIVE)
    return None


_HEAD_RULES: tuple[Callable[..., ScoreDelta | None], ...] = (
    score_unique_noun,
    score_genitive_demotion,
    score_first_among_genitive,
)


def _total(candidate: ResolvedToken, all_nouns: tuple[ResolvedToken, ...]) -> int:
    """Суммировать очки по всем правилам."""
    total = 0
    for rule in _HEAD_RULES:
        delta = rule(candidate, all_nouns)
        if delta is not None:
            total += delta.points
    return total


# ── Head selection (Etapa 2b + 6) ────────────────────────────────────────────


def _pick_head(resolved: list[ResolvedToken]) -> tuple[ResolvedToken | None, tuple[ResolvedToken, ...]]:
    """Выбрать head среди NOUN-кандидатов. Вернуть (head, ambiguous_candidates)."""
    nouns = tuple(r for r in resolved if r.is_noun)
    if not nouns:
        return None, ()

    if len(nouns) == 1:
        return nouns[0], ()

    # Score each noun candidate
    scored = [(n, _total(n, nouns)) for n in nouns]
    max_score = max(s for _, s in scored)
    winners = [n for n, s in scored if s == max_score]

    if len(winners) == 1:
        return winners[0], ()

    # Tie → AMBIGUOUS_HEAD
    return None, tuple(winners)


# ── Modifier classification (Etapa 7) ────────────────────────────────────────


def score_agrees_with_head(adj: ResolvedToken, head: ResolvedToken) -> ScoreDelta | None:
    """Прилагательное — модификатор, если согласовано с head."""
    if adj.source is None or head.source is None:
        return None
    if _adj_agrees_with_noun(adj.source, head.source):
        return ScoreDelta(reason=Reason.AGREES_WITH_NEIGHBOR_NOUN, points=_POINTS_AGREEMENT)
    return None


def _classify_modifiers(
    resolved: list[ResolvedToken],
    head: ResolvedToken,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Разделить токены на adj_modifiers и noun_modifiers после выбора head."""
    adj_mods: list[str] = []
    noun_mods: list[str] = []

    for r in resolved:
        if r is head:
            continue
        if r.is_adj:
            adj_mods.append(r.normal_form)
        elif r.is_noun:
            noun_mods.append(r.normal_form)

    return tuple(sorted(adj_mods)), tuple(sorted(noun_mods))


# ── Descriptor builder (unchanged interface) ─────────────────────────────────


def _build_descriptor(
    thing_phrase: str,
    head: ResolvedToken,
    adj_mods: tuple[str, ...],
    noun_mods: tuple[str, ...],
) -> ThingDescriptor:
    """Собрать ThingDescriptor из результатов разбора."""
    return ThingDescriptor(
        display=thing_phrase,
        detected_head=head.normal_form,
        adj_modifiers=adj_mods,
        noun_modifiers=noun_mods,
    )


# ── Public API ───────────────────────────────────────────────────────────────


def decompose(thing_phrase: str) -> DecomposeResult:
    """Разобрать именную группу на головное существительное и модификаторы."""
    tokens, _raw_words = _parse_tokens(thing_phrase)
    resolved = _resolve_pos(tokens)

    head, ambiguous = _pick_head(resolved)

    if head is not None:
        adj_mods, noun_mods = _classify_modifiers(resolved, head)
        logger.debug("decompose OK: phrase=%s, head=%s", thing_phrase, head.normal_form)
        return DecomposeResult(
            descriptor=_build_descriptor(thing_phrase, head, adj_mods, noun_mods),
            status=DecomposeStatus.OK,
        )

    nouns = [r for r in resolved if r.is_noun]
    if not nouns:
        logger.warning("decompose NO_HEAD: phrase=%s", thing_phrase)
        return DecomposeResult(descriptor=None, status=DecomposeStatus.NO_HEAD)

    candidates = tuple(r.normal_form for r in ambiguous)
    logger.warning("decompose AMBIGUOUS_HEAD: phrase=%s, candidates=%s", thing_phrase, candidates)
    return DecomposeResult(
        descriptor=None,
        status=DecomposeStatus.AMBIGUOUS_HEAD,
        candidates=candidates,
    )
