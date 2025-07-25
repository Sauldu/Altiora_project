# src/models/starcoder2/code_generator.py
"""Module de génération de code de test Playwright en parallèle avec cache et métriques.

Ce module fournit un pool de générateurs de code basés sur StarCoder2 pour
produire des tests Playwright à partir de scénarios. Il intègre un cache Redis
pour éviter la régénération de tests identiques et expose des métriques Prometheus.
"""

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

from src.utils.compression import compress_data, decompress_data
from src.models.starcoder2.starcoder2_interface import (
    StarCoder2OllamaInterface,
    PlaywrightTestConfig,
    TestType,
)

# ------------------------------------------------------------------
# Configuration du Logging
# ------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Métriques Prometheus
# ------------------------------------------------------------------
TESTS_GENERATED = Counter("altiora_tests_generated_total", "Nombre total de tests Playwright générés.")
GEN_TIME = Histogram("altiora_generation_seconds", "Temps de génération d'un test Playwright par StarCoder2.")
CACHE_HITS = Counter("altiora_cache_hits_total", "Nombre de fois où un test a été récupéré du cache Redis.")

# ------------------------------------------------------------------
# Configuration dynamique
# ------------------------------------------------------------------
# Nombre maximal de requêtes LLM parallèles. Limité par le nombre de cœurs CPU ou une valeur fixe.
MAX_PARALLEL_LLM = min(12, os.cpu_count() or 1)
# Durée de vie (TTL) des entrées de cache Redis en secondes.
REDIS_TTL = int(os.getenv("REDIS_TTL", 600))


# ------------------------------------------------------------------
# Modèle de tâche
# ------------------------------------------------------------------

@dataclass(slots=True)
class TestTask:
    """Représente une tâche de génération de test pour StarCoder2."""
    scenario: Dict[str, Any] = Field(..., description="Le scénario de test à partir duquel générer le code.")
    config: PlaywrightTestConfig = Field(..., description="La configuration spécifique pour la génération du test Playwright.")
    test_type: TestType = Field(..., description="Le type de test à générer (E2E, API, etc.).")


class TestGeneratorPool:
    """Pool de générateurs de tests Playwright avec gestion parallèle, cache Redis et métriques."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialise le pool de générateurs de tests.

        Args:
            redis_url: L'URL de connexion au serveur Redis pour le cache.
        """
        self.redis = redis.from_url(redis_url, decode_responses=False) # decode_responses=False pour stocker des bytes compressés.
        self.semaphore = asyncio.Semaphore(MAX_PARALLEL_LLM) # Limite la concurrence des appels LLM.
        self.starcoder = StarCoder2OllamaInterface() # Instance de l'interface StarCoder2.

    async def start(self) -> None:
        """Initialise l'interface StarCoder2. Doit être appelé avant d'utiliser le pool."""
        await self.starcoder.initialize()

    async def stop(self) -> None:
        """Arrête proprement l'interface StarCoder2 et ferme la connexion Redis."""
        await self.starcoder.close()
        await self.redis.aclose()

    async def generate_all(self, tasks: List[TestTask]) -> List[Dict[str, Any]]:
        """Génère des tests pour une liste de tâches en parallèle, en utilisant le cache."

        Args:
            tasks: Une liste d'objets `TestTask` représentant les tests à générer.

        Returns:
            Une liste de dictionnaires, chaque dictionnaire contenant le code du test généré
            et ses métadonnées.
        """
        # Génère une clé de cache unique pour le lot de tâches.
        key = f"test_batch_{hash(json.dumps([asdict(t) for t in tasks], sort_keys=True))}"

        # Tente de récupérer le résultat du cache Redis.
        cached = await self.redis.get(key)
        if cached:
            try:
                CACHE_HITS.inc() # Incrémente le compteur de hits du cache.
                return json.loads(decompress_data(cached)) # Décompresse et décode le JSON.
            except (zstd.ZstdError, redis.exceptions.RedisError) as e:
                logger.warning(f"Cache corrompu pour la clé {key} – régénération nécessaire : {e}")

        # Si non trouvé dans le cache ou corrompu, génère les tests en parallèle.
        coros = [self._generate_one(task) for task in tasks]
        results = await asyncio.gather(*coros, return_exceptions=False) # `return_exceptions=False` pour propager les erreurs.

        # Compresse et sauvegarde les résultats dans le cache Redis.
        compressed = compress_data(json.dumps(results))
        await self.redis.set(key, compressed, ex=REDIS_TTL)

        # Force le garbage collection si l'option est activée (utile pour la gestion de la mémoire).
        if os.getenv("ENABLE_GC", "0") == "1":
            gc.collect()

        return results

    async def _generate_one(self, task: TestTask) -> Dict[str, Any]:
        """Génère un seul test Playwright à partir d'une tâche donnée."

        Args:
            task: L'objet `TestTask` contenant le scénario et la configuration.

        Returns:
            Un dictionnaire contenant le code du test généré et ses métadonnées.
        """
        async with self.semaphore: # Acquis un jeton du sémaphore pour limiter la concurrence.
            with GEN_TIME.time(): # Mesure le temps de génération.
                code = await self.starcoder.generate_playwright_test(
                    scenario=task.scenario,
                    config=task.config,
                    test_type=task.test_type,
                )
                TESTS_GENERATED.inc() # Incrémente le compteur de tests générés.
            return code


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # Assurez-vous que Redis est lancé et accessible.
        # Assurez-vous que Ollama est lancé et que le modèle StarCoder2 est pull.

        pool = TestGeneratorPool()
        await pool.start()

        sample_scenario = {
            "titre": "Connexion utilisateur",
            "objectif": "Vérifier la connexion réussie avec des identifiants valides.",
            "etapes": [
                "Naviguer vers la page de connexion",
                "Saisir l'email et le mot de passe",
                "Cliquer sur le bouton de connexion"
            ]
        }
        sample_config = PlaywrightTestConfig(browser="chromium", use_page_object=True)

        tasks = [
            TestTask(scenario=sample_scenario, config=sample_config, test_type=TestType.E2E),
            TestTask(scenario=sample_scenario, config=sample_config, test_type=TestType.E2E),
            # Ajoutez d'autres tâches pour tester la parallélisation et le cache.
        ]

        print("\n--- Génération des tests (première fois, devrait être lent) ---")
        results1 = await pool.generate_all(tasks)
        for i, res in enumerate(results1):
            print(f"Test {i+1} généré :\n{res.get('code')[:200]}...")

        print("\n--- Génération des tests (deuxième fois, devrait être rapide grâce au cache) ---")
        results2 = await pool.generate_all(tasks)
        for i, res in enumerate(results2):
            print(f"Test {i+1} généré (depuis cache) :\n{res.get('code')[:200]}...")

        await pool.stop()
        print("Démonstration du pool de générateurs de tests terminée.")

    asyncio.run(demo())