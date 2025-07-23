# src/core/async_pipeline.py
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class AsyncPipeline:
    """
    Lightweight async pipeline with:
    • configurable concurrency
    • graceful error handling
    • optional custom processor
    """

    def __init__(
            self,
            *,
            max_concurrent: int = 4,
            processor: Callable[[Any], Awaitable[None]] | None = None,
    ) -> None:
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        self.workers: list[asyncio.Task[None]] = []
        self.max_concurrent = max_concurrent
        self.processor = processor or self._default_processor

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Start worker coroutines."""
        for idx in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker(f"worker-{idx}"))
            self.workers.append(worker)
        logger.info("Started %d pipeline workers", self.max_concurrent)

    async def stop(self) -> None:
        """Cancel all workers gracefully."""
        for w in self.workers:
            w.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        logger.info("Pipeline shut down")

    async def submit(self, task: Any) -> None:
        """Enqueue a task."""
        await self.queue.put(task)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    async def _worker(self, name: str) -> None:
        """Generic worker loop."""
        while True:
            try:
                task = await self.queue.get()
                await self.processor(task)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Worker %s failed to process task: %s", name, e)
                self.queue.task_done()

    # ------------------------------------------------------------------
    # Default processor (can be overridden)
    # ------------------------------------------------------------------
    @staticmethod
    async def _default_processor(task: Any) -> None:
        """Fallback processor when none is provided."""
        logger.warning("No custom processor provided – dropping task: %s", task)
