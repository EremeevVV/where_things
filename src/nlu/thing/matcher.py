from __future__ import annotations

from src.nlu.thing.canonicalizer import CanonicalThing


def canonical_key(thing: CanonicalThing) -> str:
    """Построить ключ идентичности вещи для точного сравнения."""
    all_mods = thing.adj_modifiers + thing.canonical_noun_modifiers
    sorted_mods = sorted(all_mods)
    joined = ",".join(sorted_mods)
    return f"{thing.canonical_head}#{joined}"
