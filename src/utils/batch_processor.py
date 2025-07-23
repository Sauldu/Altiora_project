# src/utils/batch_processor.py
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, List, Optional, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class OptimizedBatchProcessor:
    """
    CPU-friendly batch processor with:
    - configurable batch size
    - semaphore-based concurrency cap
    - optional progress callback
    """

    def __init__(self, *, batch_size: int = 10, max_concurrent: int = 5) -> None:
        if batch_size <= 0 or max_concurrent <= 0:
            raise ValueError("batch_size and max_concurrent must be positive integers")

        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def process(
        self,
        items: List[T],
        processor: Callable[[T], Awaitable[R]],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[R]:
        """
        Process `items` in batches using `processor`.

        Args:
            items: list of inputs
            processor: async callable applied to each item
            progress_callback: sync callable invoked with (processed, total)

        Returns:
            list of results in the same order as `items`
        """
        results: List[R] = []
        total = len(items)

        for start in range(0, total, self.batch_size):
            end = start + self.batch_size
            batch = items[start:end]

            async with asyncio.TaskGroup() as tg:
                tasks = [
                    tg.create_task(self._process_with_semaphore(item, processor))
                    for item in batch
                ]

            # Preserve original order
            results.extend(task.result() for task in tasks)

            if progress_callback:
                progress_callback(min(end, total), total)

        return results

    async def _process_with_semaphore(
        self, item: T, processor: Callable[[T], Awaitable[R]]
    ) -> R:
        async with self.semaphore:
            return await processor(item)