from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from src.nlu.thing.decomposer import ThingDescriptor


@dataclass(frozen=True)
class CanonicalThing:
    """Каноническое (поисковое) представление вещи."""

    display: str
    canonical_head: str
    adj_modifiers: tuple[str, ...]
    canonical_noun_modifiers: tuple[str, ...]


def canonicalize(
    td: ThingDescriptor | CanonicalThing,
    mapper: Mapping[str, str],
) -> CanonicalThing:
    """Канонизировать головное слово и именные модификаторы через словарь."""
    if isinstance(td, CanonicalThing):
        head = td.canonical_head
        noun_mods = td.canonical_noun_modifiers
    else:
        head = td.detected_head
        noun_mods = td.noun_modifiers

    canonical_head = mapper.get(head, head)
    canonical_noun_modifiers = tuple(sorted(mapper.get(nm, nm) for nm in noun_mods))
    return CanonicalThing(
        display=td.display,
        canonical_head=canonical_head,
        adj_modifiers=td.adj_modifiers,
        canonical_noun_modifiers=canonical_noun_modifiers,
    )
