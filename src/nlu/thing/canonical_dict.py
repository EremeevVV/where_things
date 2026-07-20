from __future__ import annotations

from types import MappingProxyType

CANONICAL_DICT: MappingProxyType[str, str] = MappingProxyType(
    {
        "смартфон": "телефон",
        "мобильник": "телефон",
        "айфон": "телефон",
    }
)
