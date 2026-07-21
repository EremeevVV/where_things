from __future__ import annotations

import logging
from dataclasses import dataclass

from src.nlu.thing.canonical_dict import CANONICAL_DICT
from src.nlu.thing.canonicalizer import canonicalize
from src.nlu.thing.decomposer import DecomposeStatus, decompose
from src.nlu.thing.matcher import canonical_key

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NormalizedThing:
    """Result of normalizing a raw thing phrase."""

    display_name: str
    canonical_key: str
    status: DecomposeStatus


def normalize_thing(raw: str) -> NormalizedThing:
    """Единственная точка вызова decompose/canonicalize/canonical_key."""
    result = decompose(raw)
    if result.status == DecomposeStatus.OK and result.descriptor is not None:
        ct = canonicalize(result.descriptor, CANONICAL_DICT)
        logger.info("normalize OK: raw=%s, key=%s", raw, canonical_key(ct))
        return NormalizedThing(
            display_name=raw,
            canonical_key=canonical_key(ct),
            status=result.status,
        )
    logger.warning("normalize %s: raw=%s", result.status, raw)
    return NormalizedThing(
        display_name=raw,
        canonical_key=raw,
        status=result.status,
    )
