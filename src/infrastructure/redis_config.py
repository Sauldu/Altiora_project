# src/infrastructure/redis_config.py
import redis.asyncio as redis
from typing import Optional
from configs.config_module import get_settings


class RedisManager:
    """Centralized Redis client management"""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[redis.Redis] = None

    async def get_client(self) -> redis.Redis:
        """Get or create Redis client"""
        if not self._client:
            self._client = await redis.from_url(
                self.settings.redis_url,
                password=self.settings.redis_password,
                decode_responses=True,
                max_connections=10
            )
        return self._client

    async def close(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()


# Singleton instance
_redis_manager = RedisManager()


async def get_redis_client() -> redis.Redis:
    """Get Redis client instance"""
    return await _redis_manager.get_client()