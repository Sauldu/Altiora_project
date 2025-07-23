# tests/performance/test_redis_performance.py
"""
Tests de performance Redis pour le cache
"""

import asyncio
import redis.asyncio as redis
import time
import json
import pytest
from typing import List, Dict


class RedisPerformanceTester:
    """Testeur de performance pour Redis"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url

    async def test_cache_throughput(self, num_operations: int = 10000):
        """Test le débit du cache Redis"""

        client = await redis.from_url(self.redis_url, decode_responses=True)

        metrics = {
            "total_operations": num_operations,
            "writes_per_second": 0,
            "reads_per_second": 0,
            "error_rate": 0,
            "memory_usage": 0
        }

        test_data = {"test": "data", "timestamp": time.time()}

        # Test écriture
        start_time = time.time()
        write_tasks = []
        for i in range(num_operations):
            task = client.setex(f"test_key_{i}", 3600, json.dumps(test_data))
            write_tasks.append(task)

        write_results = await asyncio.gather(*write_tasks, return_exceptions=True)
        write_duration = time.time() - start_time

        successful_writes = sum(1 for r in write_results if r is True)
        metrics["writes_per_second"] = successful_writes / write_duration

        # Test lecture
        start_time = time.time()
        read_tasks = []
        for i in range(num_operations):
            task = client.get(f"test_key_{i}")
            read_tasks.append(task)

        read_results = await asyncio.gather(*read_tasks, return_exceptions=True)
        read_duration = time.time() - start_time

        successful_reads = sum(1 for r in read_results if r is not None)
        metrics["reads_per_second"] = successful_reads / read_duration

        # Mémoire
        info = await client.info("memory")
        metrics["memory_usage"] = info.get("used_memory_human", "0")

        await client.aclose()

        return metrics

    async def test_cache_ttl_performance(self):
        """Test des TTL et expiration"""

        client = await redis.from_url(self.redis_url)

        # Créer 1000 clés avec TTL différents
        tasks = []
        for i in range(1000):
            ttl = 1 + (i % 10)  # TTL de 1 à 10 secondes
            task = client.setex(f"ttl_test_{i}", ttl, f"data_{i}")
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Attendre et vérifier l'expiration
        await asyncio.sleep(11)

        remaining = await client.keys("ttl_test_*")

        return {
            "initial_keys": 1000,
            "remaining_keys": len(remaining),
            "expired_keys": 1000 - len(remaining)
        }


@pytest.mark.performance
@pytest.mark.asyncio
async def test_redis_cache_performance():
    """Test de performance du cache Redis"""

    tester = RedisPerformanceTester()

    # Test de débit
    throughput_metrics = await tester.test_cache_throughput(1000)

    assert throughput_metrics["writes_per_second"] > 500
    assert throughput_metrics["reads_per_second"] > 1000

    # Test TTL
    ttl_metrics = await tester.test_cache_ttl_performance()

    assert ttl_metrics["expired_keys"] >= 900  # 90% expired