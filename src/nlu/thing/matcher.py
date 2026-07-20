from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.nlu.thing.canonicalizer import CanonicalThing

MODIFIER_WEIGHT_NOUN = 0.7
MODIFIER_WEIGHT_ADJ = 0.7
NO_OVERLAP_SCORE = 0.0


def canonical_key(thing: CanonicalThing) -> str:
    """Построить ключ идентичности вещи для точного сравнения."""
    all_mods = thing.adj_modifiers + thing.canonical_noun_modifiers
    sorted_mods = sorted(all_mods)
    joined = ",".join(sorted_mods)
    return f"{thing.canonical_head}#{joined}"


@dataclass(frozen=True)
class SearchResult:
    """Результат сопоставления запроса с кандидатами."""

    status: Literal["exact", "ranked", "ambiguous", "empty"]
    matches: tuple[CanonicalThing, ...]
    scores: tuple[float, ...] = ()


def _overlap(mods_a: tuple[str, ...], mods_b: tuple[str, ...]) -> float:
    """Overlap coefficient: |A∩B| / min(|A|,|B|)."""
    if not mods_a or not mods_b:
        return NO_OVERLAP_SCORE
    set_a, set_b = set(mods_a), set(mods_b)
    intersection = len(set_a & set_b)
    return intersection / min(len(set_a), len(set_b))


def _score_candidates(
    query: CanonicalThing,
    same_head: list[CanonicalThing],
) -> list[tuple[CanonicalThing, float]]:
    """Score candidates by modifier overlap."""
    scored: list[tuple[CanonicalThing, float]] = []
    for cand in same_head:
        adj_score = _overlap(query.adj_modifiers, cand.adj_modifiers)
        noun_score = _overlap(query.canonical_noun_modifiers, cand.canonical_noun_modifiers)
        score = adj_score * MODIFIER_WEIGHT_ADJ + noun_score * MODIFIER_WEIGHT_NOUN
        scored.append((cand, score))
    return scored


def _find_exact(
    query_key: str,
    candidates: list[CanonicalThing],
) -> list[CanonicalThing]:
    """Найти кандидатов с точным совпадением ключа."""
    return [cand for cand in candidates if canonical_key(cand) == query_key]


def _rank_matches(
    query: CanonicalThing,
    same_head: list[CanonicalThing],
) -> SearchResult:
    """Ранжировать кандидатов с одинаковым главным словом по скору."""
    scored = _score_candidates(query, same_head)
    scored.sort(key=lambda pair: pair[1], reverse=True)
    max_score = scored[0][1]
    top = [cand for cand, score in scored if score == max_score]
    if len(top) > 1:
        return SearchResult(
            status="ambiguous",
            matches=tuple(top),
            scores=tuple(max_score for _ in top),
        )
    return SearchResult(
        status="ranked",
        matches=tuple(top),
        scores=(max_score,),
    )


def match(query: CanonicalThing, candidates: list[CanonicalThing]) -> SearchResult:
    """Сопоставить запрос со списком кандидатов пользователя."""
    exact = _find_exact(canonical_key(query), candidates)
    if exact:
        return SearchResult(status="exact", matches=tuple(exact))

    same_head = [cand for cand in candidates if cand.canonical_head == query.canonical_head]
    if not same_head:
        return SearchResult(status="empty", matches=())

    return _rank_matches(query, same_head)
