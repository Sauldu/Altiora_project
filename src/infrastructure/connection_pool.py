# src/infrastructure/connection_pool.py
import asyncio
from contextlib import asynccontextmanager


class OllamaConnectionPool:
    def __init__(self, host: str, port: int, max_connections: int = 10):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self._pool = asyncio.Queue(maxsize=max_connections)
        self._initialized = False

    async def initialize(self):
        for _ in range(self.max_connections):
            client = await self._create_client()
            await self._pool.put(client)
        self._initialized = True

    @asynccontextmanager
    async def acquire(self):
        client = await self._pool.get()
        try:
            yield client
        finally:
            await self._pool.put(client)