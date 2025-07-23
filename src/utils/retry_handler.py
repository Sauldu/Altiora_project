# src/utils/retry_handler.py
import asyncio
import logging
from functools import wraps
from typing import Callable, Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class RetryHandler:
    """Gestionnaire centralisé pour les retries"""

    @staticmethod
    def with_retry(
            max_attempts: int = 3,
            backoff_factor: float = 2.0,
            max_delay: float = 30.0,
            exceptions: tuple = (Exception,)
    ):
        """Décorateur de retry configurable"""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            @retry(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=backoff_factor, max=max_delay),
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

    @staticmethod
    async def exponential_backoff(
            attempt: int,
            base_delay: float = 1.0,
            max_delay: float = 60.0
    ) -> float:
        """Calcul du délai exponentiel"""
        delay = min(base_delay * (2 ** attempt), max_delay)
        await asyncio.sleep(delay)
        return delay
