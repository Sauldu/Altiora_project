# src/error_management.py
"""
Centralized error handling and retry for Altiora
Async-first, encrypted, circuit-breaker & context manager.
"""

import json
import logging
import os
import traceback
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Dict, Callable, Optional

import aiofiles
from cryptography.fernet import Fernet  # lightweight symmetric crypto
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
ERROR_CONFIG = {
    "max_retries": int(os.getenv("MAX_RETRIES", 3)),
    "backoff_factor": float(os.getenv("BACKOFF_FACTOR", 2.0)),
    "circuit_breaker_timeout": int(os.getenv("CB_TIMEOUT", 60)),
    "log_file": Path(os.getenv("ERROR_LOG", "logs/errors.jsonl")),
    "encryption_key": os.getenv("LOGS_ENCRYPTION_KEY"),
}


# ------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------
class AltioraError(Exception):
    """Base Altiora exception."""


class ServiceError(AltioraError):
    """External service errors."""


class ValidationError(AltioraError):
    """Business-rule validation errors."""


# ------------------------------------------------------------------
# Encryption helper
# ------------------------------------------------------------------
class CryptoHelper:
    def __init__(self, key: Optional[str] = None):
        self.key = key or Fernet.generate_key()
        self.fernet = Fernet(self.key.encode() if isinstance(self.key, str) else self.key)

    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
        return self.fernet.encrypt(payload).decode()

    def decrypt_dict(self, token: str) -> Dict[str, Any]:
        return json.loads(self.fernet.decrypt(token.encode()))


crypto = CryptoHelper(ERROR_CONFIG["encryption_key"])


# ------------------------------------------------------------------
# Retry Handler
# ------------------------------------------------------------------
class RetryHandler:
    @staticmethod
    def with_retry(
            max_attempts: int = ERROR_CONFIG["max_retries"],
            exceptions: tuple = (Exception,),
    ):
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            @retry(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(
                    multiplier=ERROR_CONFIG["backoff_factor"], max=30
                ),
                retry=lambda exc: isinstance(exc, exceptions),  # ✅ callable
            )
            async def wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logger.warning("Retry %s: %s", func.__name__, e)
                    raise

            return wrapper

        return decorator


# ------------------------------------------------------------------
# Circuit Breaker
# ------------------------------------------------------------------
class CircuitBreaker:
    def __init__(
            self,
            failure_threshold: int = 5,
            timeout: int = ERROR_CONFIG["circuit_breaker_timeout"],
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self._failures: Dict[str, int] = {}
        self._last_failure: Dict[str, datetime] = {}
        self._is_open: Dict[str, bool] = {}

    async def call_with_protection(
            self,
            service_name: str,
            coro: Callable,
            *args,
            **kwargs,
    ) -> Any:
        if self._is_open.get(service_name, False):
            if (
                    datetime.now() - self._last_failure.get(service_name, datetime.min)
            ) < timedelta(seconds=self.timeout):
                raise ServiceError(f"Circuit breaker open for {service_name}")
            self.reset(service_name)

        try:
            result = await coro(*args, **kwargs)
            self.reset(service_name)
            return result
        except Exception:
            self._record_failure(service_name)
            if self._failures.get(service_name, 0) >= self.failure_threshold:
                self._is_open[service_name] = True
                self._last_failure[service_name] = datetime.now()
            raise

    def reset(self, service_name: str) -> None:
        self._failures[service_name] = 0
        self._is_open[service_name] = False

    def _record_failure(self, service_name: str) -> None:
        self._failures[service_name] = self._failures.get(service_name, 0) + 1


# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
class ErrorLogger:
    def __init__(self, log_file: Path = ERROR_CONFIG["log_file"]) -> None:
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    async def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {},
        }
        async with aiofiles.open(self.log_file, "a") as f:
            await f.write(crypto.encrypt_dict(entry) + "\n")
        logger.error("Error logged: %s", entry["error_message"])


class EncryptedLogger(ErrorLogger):
    async def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        await super().log_error(error, context)


# ------------------------------------------------------------------
# Context Manager
# ------------------------------------------------------------------
class ErrorContext:
    def __init__(self, operation: str, **kwargs: Any) -> None:
        self.operation = operation
        self.context = kwargs

    async def __aenter__(self) -> "ErrorContext":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_val:
            tb = traceback.format_exception(exc_type, exc_val, exc_tb)
            logger.error(
                "Unhandled in %s",
                self.operation,
                extra={"context": self.context, "traceback": tb},
            )
            # Placeholder – hook to external monitoring here
            # await send_to_monitoring(...)
        return False  # propagate


# ------------------------------------------------------------------
# Singletons
# ------------------------------------------------------------------
error_logger = EncryptedLogger()
circuit_breaker = CircuitBreaker()
