from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.nlu.thing.canonicalizer import CanonicalThing

MODIFIER_WEIGHT_NOUN = 0.7
MODIFIER_WEIGHT_ADJ = 0.7


def canonical_key(t: CanonicalThing) -> str:
    """Построить ключ идентичности вещи для точного сравнения."""
    all_mods = t.adj_modifiers + t.canonical_noun_modifiers
    sorted_mods = sorted(all_mods)
    return f"{t.canonical_head}#{','.join(sorted_mods)}"


@dataclass(frozen=True)
class SearchResult:
    """Результат сопоставления запроса с кандидатами."""

    status: Literal["exact", "ranked", "ambiguous", "empty"]
    matches: tuple[CanonicalThing, ...]
    scores: tuple[float, ...] = ()


def _overlap(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """Overlap coefficient: |A∩B| / (min(|A|,|B|) + eps)."""
    if not a or not b:
        return 0.0
    set_a, set_b = set(a), set(b)
    intersection = len(set_a & set_b)
    return intersection / min(len(set_a), len(set_b))


def match(query: CanonicalThing, candidates: list[CanonicalThing]) -> SearchResult:
    """Сопоставить запрос со списком кандидатов пользователя."""
    query_key = canonical_key(query)
    exact_matches = [c for c in candidates if canonical_key(c) == query_key]
    if exact_matches:
        return SearchResult(
            status="exact",
            matches=tuple(exact_matches),
        )

    same_head = [c for c in candidates if c.canonical_head == query.canonical_head]
    if not same_head:
        return SearchResult(status="empty", matches=())

    scored: list[tuple[CanonicalThing, float]] = []
    for c in same_head:
        adj_score = _overlap(query.adj_modifiers, c.adj_modifiers)
        noun_score = _overlap(query.canonical_noun_modifiers, c.canonical_noun_modifiers)
        score = adj_score * MODIFIER_WEIGHT_ADJ + noun_score * MODIFIER_WEIGHT_NOUN
        scored.append((c, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    max_score = scored[0][1]
    top = [c for c, s in scored if s == max_score]

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
