# src/monitoring/structured_logger.py
import logging
import sys
from typing import Any, Dict

from pythonjsonlogger import jsonlogger  # pip install python-json-logger


class StructuredLogger:
    """
    Central JSON logger for Altiora.
    Usage:
        logger.info("sfd_processed",
                    extra={"sfd_id": "123", "duration_ms": 450, "model": "qwen3"})
    """

    def __init__(self, name: str = "altiora") -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.INFO)

        # JSON formatter
        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s"
        )
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)
        self._logger.propagate = False

    def info(self, message: str, extra: Dict[str, Any] | None = None) -> None:
        self._logger.info(message, extra=extra or {})

    def error(self, message: str, extra: Dict[str, Any] | None = None) -> None:
        self._logger.error(message, extra=extra or {})

    def warning(self, message: str, extra: Dict[str, Any] | None = None) -> None:
        self._logger.warning(message, extra=extra or {})


# Singleton
logger = StructuredLogger()
