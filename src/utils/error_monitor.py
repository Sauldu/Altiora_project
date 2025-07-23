# src/utils/error_monitor.py
"""
Architecture de gestion d'erreurs et retry pour Altiora
Module centralisé utilisé par tous les composants
"""

import json
import logging
import traceback
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Dict, Any, Callable

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
ERROR_CONFIG = {
    "max_retries": 3,
    "backoff_factor": 2.0,
    "circuit_breaker_timeout": 60,
    "log_file": "logs/errors.jsonl"
}


# ------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------
class AltioraError(Exception):
    """Base exception pour Altiora"""
    pass


class ServiceError(AltioraError):
    """Erreurs de service externe"""
    pass


class ValidationError(AltioraError):
    """Erreurs de validation métier"""
    pass


# ------------------------------------------------------------------
# Retry Handler
# ------------------------------------------------------------------
class RetryHandler:
    """Gestionnaire de retry centralisé"""

    @staticmethod
    def with_retry(max_attempts: int = 3, exceptions: tuple = (Exception,)):
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            @retry(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=2.0, max=30),
                retry=exceptions
            )
            async def wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    logger.warning(f"Retry {func.__name__}: {e}")
                    raise

            return wrapper

        return decorator


# ------------------------------------------------------------------
# Circuit Breaker
# ------------------------------------------------------------------
class CircuitBreaker:
    """Protection contre les cascades d'erreurs"""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures: Dict[str, int] = {}
        self.last_failure: Dict[str, datetime] = {}
        self.is_open: Dict[str, bool] = {}

    async def call_with_protection(
            self,
            service_name: str,
            coro: Callable,
            *args, **kwargs
    ) -> Any:
        if self.is_open.get(service_name, False):
            if datetime.now() - self.last_failure.get(service_name, datetime.min) < timedelta(seconds=self.timeout):
                raise ServiceError(f"Circuit breaker open for {service_name}")
            self.reset(service_name)

        try:
            result = await coro(*args, **kwargs)
            self.reset(service_name)
            return result
        except Exception as e:
            self._record_failure(service_name)
            if self.failures.get(service_name, 0) >= self.failure_threshold:
                self.is_open[service_name] = True
                self.last_failure[service_name] = datetime.now()
            raise

    def reset(self, service_name: str):
        self.failures[service_name] = 0
        self.is_open[service_name] = False

    def _record_failure(self, service_name: str):
        self.failures[service_name] = self.failures.get(service_name, 0) + 1


# ------------------------------------------------------------------
# Error Logger
# ------------------------------------------------------------------
class ErrorLogger:
    """Logging centralisé des erreurs"""

    def __init__(self, log_file: str = ERROR_CONFIG["log_file"]):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(exist_ok=True)

    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {},
            "stack_trace": traceback.format_exc()
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(error_entry) + "\n")
        logger.error(f"Error logged: {error_entry}")


# ------------------------------------------------------------------
# Instances globales
# ------------------------------------------------------------------
error_logger = ErrorLogger()
circuit_breaker = CircuitBreaker()
