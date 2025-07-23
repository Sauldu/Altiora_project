# src/code_generator.py
import asyncio
import gc
import json
import logging
import os
from dataclasses import asdict, dataclass
from typing import List, Dict, Any

import redis.asyncio as redis
import zstandard as zstd
from prometheus_client import Counter, Histogram

from utils.compression import compress_data, decompress_data
# 🔧 Imports corrigés
from .starcoder2_interface import (
    StarCoder2OllamaInterface,
    PlaywrightTestConfig,
    TestType,
)

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Métriques Prometheus
# ------------------------------------------------------------------
TESTS_GENERATED = Counter("altiora_tests_generated_total", "Nombre de tests générés")
GEN_TIME = Histogram("altiora_generation_seconds", "Temps de génération d’un test")
CACHE_HITS = Counter("altiora_cache_hits_total", "Nombre de hits Redis")

# ------------------------------------------------------------------
# Configuration dynamique
# ------------------------------------------------------------------
MAX_PARALLEL_LLM = min(12, os.cpu_count() or 1)
REDIS_TTL = int(os.getenv("REDIS_TTL", 600))


# ------------------------------------------------------------------
# Modèle de tâche
# ------------------------------------------------------------------

@dataclass(slots=True)
class TestTask:
    scenario: Dict[str, Any]
    config: PlaywrightTestConfig
    test_type: TestType


class TestGeneratorPool:
    """Pool de génération parallèle avec cache et métriques"""

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=False)
        self.semaphore = asyncio.Semaphore(MAX_PARALLEL_LLM)
        self.starcoder = StarCoder2OllamaInterface()

    async def start(self) -> None:
        await self.starcoder.initialize()

    async def stop(self) -> None:
        await self.starcoder.close()
        await self.redis.aclose()

    async def generate_all(self, tasks: List[TestTask]) -> List[Dict[str, Any]]:
        key = f"test_batch_{hash(json.dumps([asdict(t) for t in tasks], sort_keys=True))}"

        cached = await self.redis.get(key)
        if cached:
            try:
                CACHE_HITS.inc()
                return json.loads(decompress_data(cached))
            except (zstd.ZstdError, redis.exceptions.RedisError) as e:
                logger.warning(f"Cache corrompu – régénération : {e}")

        coros = [self._generate_one(task) for task in tasks]
        results = await asyncio.gather(*coros, return_exceptions=False)

        compressed = compress_data(json.dumps(results))
        await self.redis.set(key, compressed, ex=REDIS_TTL)

        if os.getenv("ENABLE_GC", "0") == "1":
            gc.collect()

        return results

    async def _generate_one(self, task: TestTask) -> Dict[str, Any]:
        async with self.semaphore:
            with GEN_TIME.time():
                code = await self.starcoder.generate_playwright_test(
                    scenario=task.scenario,
                    config=task.config,
                    test_type=task.test_type,
                )
                TESTS_GENERATED.inc()
            return code
