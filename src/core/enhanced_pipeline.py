# src/core/enhanced_pipeline.py
import asyncio
from typing import AsyncIterator, TypeVar, Callable

T = TypeVar('T')


class AsyncPipeline:
    def __init__(self, max_buffer_size: int = 100):
        self.max_buffer_size = max_buffer_size
        self.stages: List[Callable] = []

    def add_stage(self, func: Callable) -> 'AsyncPipeline':
        self.stages.append(func)
        return self

    async def process(self, items: AsyncIterator[T]) -> AsyncIterator[T]:
        queues = [asyncio.Queue(maxsize=self.max_buffer_size)
                  for _ in range(len(self.stages) + 1)]

        # Créer les workers pour chaque étape
        workers = []
        for i, stage in enumerate(self.stages):
            worker = asyncio.create_task(
                self._stage_worker(stage, queues[i], queues[i + 1])
            )
            workers.append(worker)

        # Alimenter la première queue
        async for item in items:
            await queues[0].put(item)

        # Signaler la fin
        await queues[0].put(None)

        # Récupérer les résultats
        while True:
            result = await queues[-1].get()
            if result is None:
                break
            yield result

        # Attendre que tous les workers terminent
        await asyncio.gather(*workers)