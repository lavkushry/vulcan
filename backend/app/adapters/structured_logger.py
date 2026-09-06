"""
Project Vulcan: Structured JSON Logging Formatter
Author: Alex Xu (Distributed Systems Lead)
Formats all application log records into structured JSON with correlation IDs
compatible with fluentbit, Datadog, and cloud log aggregators.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional


class VulcanJSONLogFormatter(logging.Formatter):
    """Formats log records into machine-readable structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "source": f"{record.filename}:{record.lineno}",
        }

        # Propagate correlation ID if attached to record
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_structured_logging(level: int = logging.INFO, use_json: bool = True) -> None:
    """Configures root logging with VulcanJSONLogFormatter."""
    handler = logging.StreamHandler()
    if use_json:
        handler.setFormatter(VulcanJSONLogFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
        ))

    root_logger = logging.getLogger("vulcan")
    root_logger.setLevel(level)
    # Avoid duplicate handlers on re-init
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)
