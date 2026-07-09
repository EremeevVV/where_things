from __future__ import annotations

import re
from enum import StrEnum


class Intent(StrEnum):
    """Намерения пользователя (NLU intents)."""

    SAVE = "SAVE"
    FIND = "FIND"
    LIST = "LIST"
    DELETE = "DELETE"
    UNKNOWN = "UNKNOWN"


def parse_intent(command: str) -> tuple[Intent, dict[str, str]]:
    """Parse command text into (intent, slots).

    Intents: SAVE, FIND, LIST, DELETE, UNKNOWN
    """
    c = command.strip().lower()

    # LIST
    if re.match(r"^(что\s+ты\s+помнишь|что\s+запомнено|список|все\s+вещи)", c):
        return Intent.LIST, {}

    # SAVE: "запомни что X лежит Y" / "запомни X лежит Y"
    m = re.match(r"^запомни,?\s*что\s+(.+?)\s+леж[иа]т\s+(.+)$", c)
    if m:
        return Intent.SAVE, {"thing": m.group(1).strip(), "place": m.group(2).strip()}

    m = re.match(r"^запомни\s+(.+?)\s+леж[иа]т\s+(.+)$", c)
    if m:
        return Intent.SAVE, {"thing": m.group(1).strip(), "place": m.group(2).strip()}

    # SAVE incomplete: "запомни что X" / "запомни X" (no place)
    m = re.match(r"^запомни,?\s*что\s+(.+)$", c)
    if m:
        return Intent.SAVE, {"thing": m.group(1).strip(), "place": ""}

    m = re.match(r"^запомни\s+(.+)$", c)
    if m:
        return Intent.SAVE, {"thing": m.group(1).strip(), "place": ""}

    # FIND: "где лежит X" / "где X"
    m = re.match(r"^где\s+леж[иа]т\s+(.+)$", c)
    if m:
        return Intent.FIND, {"thing": m.group(1).strip()}

    m = re.match(r"^где\s+(.+)$", c)
    if m:
        return Intent.FIND, {"thing": m.group(1).strip()}

    # DELETE: "забудь про X" / "забудь X"
    m = re.match(r"^забудь\s+про\s+(.+)$", c)
    if m:
        return Intent.DELETE, {"thing": m.group(1).strip()}

    m = re.match(r"^забудь\s+(.+)$", c)
    if m:
        return Intent.DELETE, {"thing": m.group(1).strip()}

    return Intent.UNKNOWN, {}
