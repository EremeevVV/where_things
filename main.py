from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, ClassVar

from aliceio import Dispatcher, Skill
from aliceio.webhook.yandex_functions import (
    OneSkillYandexFunctionsRequestHandler,
    RuntimeContext,
)

from src.db import YdbItemsRepository
from src.handlers import setup_handlers

# ── JSON formatter for Yandex Cloud Logging ───────────────────────────────────


class JsonFormatter(logging.Formatter):
    """Structured JSON logs for Yandex Cloud Logging (stdout → json_payload).

    Required fields per platform spec:
      - message/msg: entry text
      - level: TRACE | DEBUG | INFO | WARN | ERROR | FATAL
    Optional: request_id (for concurrent function call tracing).
    """

    _LEVEL_MAP: ClassVar[dict[str, str]] = {"WARNING": "WARN", "CRITICAL": "FATAL"}

    def format(self, record: logging.LogRecord) -> str:
        """Serialize LogRecord to JSON string."""
        level = self._LEVEL_MAP.get(record.levelname, record.levelname)
        log_obj: dict[str, Any] = {
            "message": record.getMessage(),
            "level": level,
            "logger": record.name,
        }
        if getattr(record, "request_id", None):
            log_obj["request_id"] = record.request_id  # type: ignore[attr-defined]
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
