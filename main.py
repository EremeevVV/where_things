from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

from aliceio import Dispatcher, Skill
from aliceio.webhook.yandex_functions import (
    OneSkillYandexFunctionsRequestHandler,
    RuntimeContext,
)

from src.db import YdbItemsRepository
from src.handlers import setup_handlers

# ── JSON formatter for Yandex Cloud Logging ───────────────────────────────────


class JsonFormatter(logging.Formatter):
    """Structured JSON logs for Yandex Cloud Logging (stdout → json_payload)."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize LogRecord to JSON string."""
        log_obj: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, ensure_ascii=False)


# ── Logging setup ─────────────────────────────────────────────────────────────

_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(JsonFormatter())

_root = logging.getLogger()
_root.setLevel(os.getenv("LOG_LEVEL", "INFO"))
_root.handlers.clear()
_root.addHandler(_stream_handler)

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
