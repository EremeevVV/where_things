from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pymorphy3

morph = pymorphy3.MorphAnalyzer()


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


def decompose(thing_phrase: str) -> DecomposeResult:
    """Разобрать именную группу на головное существительное и модификаторы."""
    tokens = [t.strip() for t in thing_phrase.split() if t.strip()]

    nouns: list[tuple[str, str]] = []
    adjs: list[str] = []

    for token in tokens:
        parsed = morph.parse(token)[0]
        tag = parsed.tag
        if "NOUN" in tag:
            nouns.append((parsed.normal_form, tag.case))
        elif "ADJF" in tag or "PRTF" in tag:
            adjs.append(parsed.normal_form)

    head_candidates = [nf for nf, case in nouns if case != "gent"]

    if not head_candidates:
        if nouns:
            head = nouns[0][0]
            noun_mods = tuple(sorted(nf for nf, _ in nouns if nf != head))
            adj_mods = tuple(sorted(adjs))
            return DecomposeResult(
                descriptor=ThingDescriptor(
                    display=thing_phrase,
                    detected_head=head,
                    adj_modifiers=adj_mods,
                    noun_modifiers=noun_mods,
                ),
                status=DecomposeStatus.OK,
            )
        return DecomposeResult(descriptor=None, status=DecomposeStatus.NO_HEAD)

    if len(head_candidates) == 1:
        head = head_candidates[0]
        noun_mods = tuple(sorted(nf for nf, _ in nouns if nf != head))
        adj_mods = tuple(sorted(adjs))
        return DecomposeResult(
            descriptor=ThingDescriptor(
                display=thing_phrase,
                detected_head=head,
                adj_modifiers=adj_mods,
                noun_modifiers=noun_mods,
            ),
            status=DecomposeStatus.OK,
        )

    return DecomposeResult(
        descriptor=None,
        status=DecomposeStatus.AMBIGUOUS_HEAD,
        candidates=tuple(head_candidates),
    )
