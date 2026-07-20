from __future__ import annotations

import logging
import os
from typing import Any

from aliceio import Dispatcher, Skill
from aliceio.webhook.yandex_functions import (
    OneSkillYandexFunctionsRequestHandler,
    RuntimeContext,
)

from src.db import YdbItemsRepository
from src.handlers import setup_handlers

logger = logging.getLogger(__name__)

# ── Skill + Dispatcher ────────────────────────────────────────────────────────

SKILL_ID = os.getenv("SKILL_ID", "")
skill = Skill(skill_id=SKILL_ID)
dp = Dispatcher(repo=YdbItemsRepository())

setup_handlers(dp)

# ── Yandex Cloud Functions handler ────────────────────────────────────────────

_handler = OneSkillYandexFunctionsRequestHandler(dp, skill)


async def handler(event: dict[str, Any], context: RuntimeContext) -> Any:
    """Yandex Cloud Functions entry point."""
    return await _handler.handle(event, context)
