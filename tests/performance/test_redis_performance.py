# tests/performance/test_redis_performance.py
"""Tests de performance pour le cache Redis.

Ce module contient des tests de performance pour évaluer le débit (throughput)
et l'efficacité de la gestion des TTL (Time-To-Live) du cache Redis.
Il simule des opérations de lecture et d'écriture concurrentes pour mesurer
les performances sous charge.
"""

import asyncio
import redis.asyncio as redis
import time
import json
import pytest
from typing import List, Dict, Any


class RedisPerformanceTester:
    """Testeur de performance pour les opérations Redis."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialise le testeur avec l'URL de connexion Redis."

        Args:
            redis_url: L'URL de connexion au serveur Redis.
        """
        self.redis_url = redis_url

    async def test_cache_throughput(self, num_operations: int = 10000) -> Dict[str, Any]:
        """Teste le débit du cache Redis en effectuant un grand nombre d'opérations de lecture/écriture."

        Args:
            num_operations: Le nombre total d'opérations de lecture et d'écriture à effectuer.

        Returns:
            Un dictionnaire contenant les métriques de performance (débit d'écriture/lecture, erreurs, mémoire).
        """
        client = await redis.from_url(self.redis_url, decode_responses=True)

        metrics = {
            "total_operations": num_operations,
            "writes_per_second": 0.0,
            "reads_per_second": 0.0,
            "error_rate": 0.0,
            "memory_usage": "0"
        }

        test_data = {"test": "data", "timestamp": time.time()}

        # --- Test d'écriture ---
        start_time = time.time()
        write_tasks = []
        for i in range(num_operations):
            task = client.setex(f"test_key_{i}", 3600, json.dumps(test_data))
            write_tasks.append(task)

        write_results = await asyncio.gather(*write_tasks, return_exceptions=True)
        write_duration = time.time() - start_time

        successful_writes = sum(1 for r in write_results if r is True)
        metrics["writes_per_second"] = successful_writes / write_duration if write_duration > 0 else 0
        metrics["error_rate"] += (num_operations - successful_writes) / num_operations

        # --- Test de lecture ---
        start_time = time.time()
        read_tasks = []
        for i in range(num_operations):
            task = client.get(f"test_key_{i}")
            read_tasks.append(task)

        read_results = await asyncio.gather(*read_tasks, return_exceptions=True)
        read_duration = time.time() - start_time

        successful_reads = sum(1 for r in read_results if r is not None and not isinstance(r, Exception))
        metrics["reads_per_second"] = successful_reads / read_duration if read_duration > 0 else 0
        metrics["error_rate"] += (num_operations - successful_reads) / num_operations

        # --- Utilisation mémoire --- 
        try:
            info = await client.info("memory")
            metrics["memory_usage"] = info.get("used_memory_human", "0")
        except Exception as e:
            logging.warning(f"Impossible de récupérer les infos mémoire de Redis : {e}")
            metrics["memory_usage"] = "N/A"

        await client.aclose()

        return metrics

    async def test_cache_ttl_performance(self) -> Dict[str, int]:
        """Teste la performance de la gestion des TTL et l'expiration des clés dans Redis."

        Returns:
            Un dictionnaire contenant le nombre de clés initiales, restantes et expirées.
        """
        client = await redis.from_url(self.redis_url)

        # Crée 1000 clés avec des TTL différents (de 1 à 10 secondes).
        tasks = []
        for i in range(1000):
            ttl = 1 + (i % 10)  # TTL de 1 à 10 secondes.
            task = client.setex(f"ttl_test_{i}", ttl, f"data_{i}")
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Attend que toutes les clés avec un TTL court expirent.
        await asyncio.sleep(11) # Attend 11 secondes pour s'assurer que toutes les clés (max TTL 10s) expirent.

        # Compte les clés restantes.
        remaining = await client.keys("ttl_test_*")

        await client.aclose()

        return {
            "initial_keys": 1000,
            "remaining_keys": len(remaining),
            "expired_keys": 1000 - len(remaining)
        }


@pytest.mark.performance
@pytest.mark.asyncio
async def test_redis_cache_performance(wait_for_services):
    """Test de performance global du cache Redis."

    Ce test combine les vérifications de débit et de TTL pour une évaluation complète.
    """

    tester = RedisPerformanceTester()

    # --- Test de débit ---
    throughput_metrics = await tester.test_cache_throughput(1000) # Exécute 1000 opérations.
    logging.info(f"Métriques de débit Redis : {throughput_metrics}")

    assert throughput_metrics["writes_per_second"] > 500, "Le débit d'écriture devrait être supérieur à 500 ops/s."
    assert throughput_metrics["reads_per_second"] > 1000, "Le débit de lecture devrait être supérieur à 1000 ops/s."

    # --- Test TTL ---
    ttl_metrics = await tester.test_cache_ttl_performance()
    logging.info(f"Métriques TTL Redis : {ttl_metrics}")

    assert ttl_metrics["expired_keys"] >= 900, "Au moins 90% des clés devraient avoir expiré."
