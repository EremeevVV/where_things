from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pymorphy3

morph = pymorphy3.MorphAnalyzer()

type NounInfo = tuple[str, str]


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


def _parse_tokens(thing_phrase: str) -> tuple[list[NounInfo], list[str]]:
    """Токенизация и морфоразбор через pymorphy3."""
    nouns: list[NounInfo] = []
    adjs: list[str] = []
    for token in thing_phrase.split():
        parsed = morph.parse(token.strip())[0]
        if "NOUN" in parsed.tag:
            nouns.append((parsed.normal_form, parsed.tag.case))
        elif "ADJF" in parsed.tag or "PRTF" in parsed.tag:
            adjs.append(parsed.normal_form)
    return nouns, adjs


def _build_descriptor(
    thing_phrase: str,
    head: str,
    nouns: list[NounInfo],
    adjs: list[str],
) -> ThingDescriptor:
    """Собрать ThingDescriptor из результатов разбора."""
    non_head = [nf for nf, _ in nouns if nf != head]
    noun_mods = tuple(sorted(non_head))
    adj_mods = tuple(sorted(adjs))
    return ThingDescriptor(
        display=thing_phrase,
        detected_head=head,
        adj_modifiers=adj_mods,
        noun_modifiers=noun_mods,
    )


def _pick_head(nouns: list[NounInfo]) -> str | None:
    """Выбрать головное слово из списка существительных."""
    non_gent = [nf for nf, case in nouns if case != "gent"]
    if len(non_gent) == 1:
        return non_gent[0]
    if not non_gent and nouns:
        return nouns[0][0]
    return None


def decompose(thing_phrase: str) -> DecomposeResult:
    """Разобрать именную группу на головное существительное и модификаторы."""
    nouns, adjs = _parse_tokens(thing_phrase)
    head = _pick_head(nouns)
    if head is not None:
        return DecomposeResult(
            descriptor=_build_descriptor(thing_phrase, head, nouns, adjs),
            status=DecomposeStatus.OK,
        )
    if not nouns:
        return DecomposeResult(descriptor=None, status=DecomposeStatus.NO_HEAD)
    return DecomposeResult(
        descriptor=None,
        status=DecomposeStatus.AMBIGUOUS_HEAD,
        candidates=tuple(nf for nf, case in nouns if case != "gent"),
    )
