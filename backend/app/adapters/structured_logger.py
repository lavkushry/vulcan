"""
Project Vulcan: Structured JSON Logging Formatter (INFRA-24)
Author: Alex Xu (Distributed Systems Lead)
Formats all application log records into structured JSON with correlation IDs
compatible with fluentbit, Datadog, and cloud log aggregators.

Configuration via environment variables:
  LOG_LEVEL  — Python log level name (default: INFO)
  LOG_FORMAT — "json" (default) or "text" for human-readable local dev
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional


class VulcanJSONLogFormatter(logging.Formatter):
    """Formats log records into machine-readable structured JSON.
    
    Propagates extra fields from log calls (e.g., correlation_id, method,
    path, status_code, duration_ms) into top-level JSON keys for Datadog
    facet indexing and fluentbit routing.
    """

    # Fields from LogRecord that are standard Python logging internals
    _RESERVED = frozenset({
        "name", "msg", "args", "created", "relativeCreated", "exc_info",
        "exc_text", "stack_info", "lineno", "funcName", "sinfo",
        "filename", "module", "pathname", "thread", "threadName",
        "process", "processName", "levelname", "levelno", "message",
        "msecs", "taskName",
    })

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "source": f"{record.filename}:{record.lineno}",
        }

        # Propagate any extra fields passed via logger.info(..., extra={...})
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                log_entry[key] = value

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_structured_logging(level: int = logging.INFO, use_json: bool = True) -> None:
    """Configures root 'vulcan' logger hierarchy with VulcanJSONLogFormatter.
    
    Args:
        level: Python logging level (default: INFO).
        use_json: If True, use JSON formatter; if False, use human-readable text.
    """
    handler = logging.StreamHandler()
    if use_json:
        handler.setFormatter(VulcanJSONLogFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
        ))

    root_logger = logging.getLogger("vulcan")
    root_logger.setLevel(level)
    # Avoid duplicate handlers on re-init (e.g., test teardown/setup cycles)
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)
