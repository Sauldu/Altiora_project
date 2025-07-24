# src/utils/retry_handler.py
import asyncio
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class RetryHandler:
    """Gestionnaire centralisé pour les retries et les circuit breakers"""

    def __init__(self, max_attempts: int = 3, backoff_factor: float = 2.0, max_delay: float = 30.0, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.open_until = None

    def with_retry(self, exceptions: tuple = (Exception,)):
        """Décorateur de retry configurable"""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            @retry(
                stop=stop_after_attempt(self.max_attempts),
                wait=wait_exponential(multiplier=self.backoff_factor, max=self.max_delay),
                retry=retry_if_exception_type(exceptions),
                reraise=True
            )
            async def wrapper(*args, **kwargs) -> Any:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    logger.warning(
                        f"Retry attempt {getattr(wrapper, '_retry_attempt', 0) + 1} "
                        f"for {func.__name__}: {str(e)}"
                    )
                    raise

            return wrapper

        return decorator

    def circuit_breaker(self, func: Callable) -> Callable:
        """Décorateur de circuit breaker"""
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if self.open_until and self.open_until > datetime.now():
                raise Exception("Circuit breaker is open")
            try:
                result = await func(*args, **kwargs)
                self.failures = 0
                return result
            except Exception as e:
                self.failures += 1
                if self.failures >= self.failure_threshold:
                    self.open_until = datetime.now() + timedelta(seconds=self.recovery_timeout)
                raise e
        return wrapper

    async def exponential_backoff(self, attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
        """Calcul du délai exponentiel"""
        delay = min(base_delay * (2 ** attempt), max_delay)
        await asyncio.sleep(delay)
        return delay


# Utilisation
retry_handler = RetryHandler()


# Exemple d'utilisation des décorateurs
@retry_handler.circuit_breaker
@retry_handler.with_retry()
async def critical_operation():
    pass
