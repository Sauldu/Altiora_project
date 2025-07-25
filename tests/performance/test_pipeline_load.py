# tests/performance/test_pipeline_load.py
"""Tests de charge complets pour le pipeline Altiora.

Ce module contient des tests de performance et de scalabilité pour le pipeline
complet de l'application Altiora (SFD → Analyse → Génération de tests).
Il mesure l'utilisation des ressources (CPU, mémoire) sous différentes charges
et vérifie la résilience du système.
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

import psutil
import pytest
import tempfile
import redis.asyncio as redis

from src.orchestrator import Orchestrator


class PipelineLoadTester:
    """Testeur de charge pour le pipeline complet d'Altiora."""

    def __init__(self):
        """Initialise le testeur de charge avec des limites de ressources par défaut."""
        self.cpu_limit = 85  # Limite d'utilisation CPU en pourcentage.
        self.memory_limit = 25  # Limite d'utilisation mémoire en Go.
        self.process = psutil.Process() # Référence au processus courant pour la surveillance.

    def monitor_resources(self) -> Dict[str, float]:
        """Surveille et retourne les métriques d'utilisation des ressources système."

        Returns:
            Un dictionnaire contenant le pourcentage d'utilisation CPU, le pourcentage
            et la quantité de mémoire utilisée (en Go), la température CPU (si disponible),
            et la mémoire utilisée par le processus courant.
        """
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_gb": memory.used / (1024 ** 3),
            "temperature": self._get_cpu_temperature(),
            "process_memory": self.process.memory_info().rss / (1024 ** 3)
        }

    @staticmethod
    def _get_cpu_temperature() -> float:
        """Récupère la température CPU (fonction factice ou dépendante de `psutil`)."

        Returns:
            La température CPU en degrés Celsius, ou 0.0 si non disponible.
        """
        try:
            temps = psutil.sensors_temperatures()
            if 'coretemp' in temps:
                # Retourne la température maximale des cœurs.
                return max([t.current for t in temps['coretemp']])
            return 0.0
        except AttributeError:
            # psutil.sensors_temperatures() n'est pas disponible sur tous les systèmes.
            return 0.0
        except Exception as e:
            logging.warning(f"Impossible de récupérer la température CPU : {e}")
            return 0.0

    def should_stop_load(self) -> bool:
        """Détermine si la génération de charge doit être arrêtée en fonction des limites de ressources."

        Returns:
            True si une limite de ressource est dépassée, False sinon.
        """
        metrics = self.monitor_resources()
        return (
                metrics["cpu_percent"] > self.cpu_limit or
                metrics["memory_gb"] > self.memory_limit or
                metrics["temperature"] > 80 # Température critique.
        )

    async def load_test_full_pipeline(self, num_concurrent: int = 20) -> Dict[str, Any]:
        """Exécute un test de charge complet sur le pipeline Altiora."

        Args:
            num_concurrent: Le nombre de requêtes de pipeline à lancer en parallèle.

        Returns:
            Un dictionnaire d'analyse des résultats de charge.
        """
        # Créer des SFD de test à partir de templates.
        sfd_templates = [
            "Spécification login: email, password, validation",
            "Spécification API: endpoints, méthodes, authentification",
            "Spécification UI: formulaires, boutons, validations"
        ]

        results = []
        orchestrator = Orchestrator() # Crée une instance de l'orchestrateur.
        await orchestrator.initialize()

        try:
            # Prépare les tâches individuelles du pipeline.
            tasks = []
            for i in range(num_concurrent):
                sfd_content = f"{sfd_templates[i % len(sfd_templates)]} - test {i}"
                task = self._single_pipeline_test(orchestrator, sfd_content, i)
                tasks.append(task)

            # Exécute les tâches par lots avec une limitation de charge.
            batch_size = 5
            for i in range(0, num_concurrent, batch_size):
                if self.should_stop_load():
                    logger.warning("Arrêt de la génération de charge en raison des limites système atteintes.")
                    break

                batch = tasks[i:i + batch_size]
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                results.extend(batch_results)

                # Petite pause pour laisser le système respirer entre les lots.
                await asyncio.sleep(2)

        finally:
            await orchestrator.close()

        return self._analyze_results(results)

    async def _single_pipeline_test(self, orchestrator: Orchestrator, sfd_content: str, index: int) -> Dict[str, Any]:
        """Exécute un seul test du pipeline et collecte ses métriques."

        Args:
            orchestrator: L'instance de l'orchestrateur à utiliser.
            sfd_content: Le contenu de la SFD pour ce test.
            index: L'index du test (pour le nom de fichier temporaire).

        Returns:
            Un dictionnaire contenant les résultats de l'exécution du test.
        """
        start_time = time.time()
        start_resources = self.monitor_resources()

        # Crée un fichier SFD temporaire pour le test.
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(sfd_content)
            sfd_path = Path(f.name)

        try:
            result = await orchestrator.run_full_pipeline(str(sfd_path))

            end_time = time.time()
            end_resources = self.monitor_resources()

            return {
                "index": index,
                "success": result["status"] == "completed",
                "duration": end_time - start_time,
                "scenarios": result.get("metrics", {}).get("scenarios_found", 0),
                "tests_generated": result.get("metrics", {}).get("tests_generated", 0),
                "cpu_usage": (start_resources["cpu_percent"] + end_resources["cpu_percent"]) / 2,
                "memory_usage": end_resources["memory_gb"],
                "error": None if result["status"] == "completed" else result.get("error")
            }

        except Exception as e:
            return {
                "index": index,
                "success": False,
                "duration": time.time() - start_time,
                "error": str(e)
            }
        finally:
            sfd_path.unlink(missing_ok=True) # S'assure que le fichier temporaire est supprimé.

    @staticmethod
    def _analyze_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyse et agrège les résultats des tests de charge."

        Args:
            results: Une liste de dictionnaires, chaque dictionnaire étant le résultat d'un test unique.

        Returns:
            Un dictionnaire récapitulatif des métriques de performance.
        """
        successful = [r for r in results if r.get("success", False)]
        failed = [r for r in results if not r.get("success", False)]

        total_tests = len(results)
        successful_count = len(successful)
        failed_count = len(failed)

        avg_duration = sum(r["duration"] for r in successful) / successful_count if successful_count > 0 else 0
        avg_scenarios = sum(r["scenarios"] for r in successful) / successful_count if successful_count > 0 else 0
        avg_tests = sum(r["tests_generated"] for r in successful) / successful_count if successful_count > 0 else 0

        # Calcul du débit (tests réussis par seconde).
        total_successful_duration = sum(r["duration"] for r in successful)
        throughput = successful_count / total_successful_duration if total_successful_duration > 0 else 0

        return {
            "total_tests": total_tests,
            "successful": successful_count,
            "failed": failed_count,
            "success_rate": (successful_count / total_tests) * 100 if total_tests > 0 else 0,
            "avg_duration": avg_duration,
            "avg_scenarios": avg_scenarios,
            "avg_tests": avg_tests,
            "throughput": throughput,
            "error_rate": (failed_count / total_tests) * 100 if total_tests > 0 else 0
        }


@pytest.mark.performance
@pytest.mark.asyncio
async def test_cpu_load_pipeline():
    """Test de charge CPU avec le pipeline complet."

    Vérifie que le pipeline peut gérer une charge CPU élevée sans dépasser les limites.
    """

    tester = PipelineLoadTester()

    # Exécute le test de charge avec 10 requêtes concurrentes.
    metrics = await tester.load_test_full_pipeline(num_concurrent=10)

    # Assertions sur les métriques de performance.
    assert metrics["success_rate"] > 80, "Le taux de succès devrait être supérieur à 80%."
    assert metrics["avg_duration"] < 120, "La durée moyenne par test devrait être inférieure à 120 secondes."
    assert metrics["throughput"] > 0.05, "Le débit devrait être supérieur à 0.05 test/seconde."

    # Vérification des ressources système après le test.
    final_metrics = tester.monitor_resources()
    assert final_metrics["cpu_percent"] < 95, "L'utilisation CPU devrait rester sous 95%."
    assert final_metrics["memory_gb"] < 28, "L'utilisation mémoire devrait rester sous 28 Go."


@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_efficiency_pipeline():
    """Test de l'efficacité mémoire du pipeline avec de gros fichiers SFD."

    Vérifie que le pipeline gère efficacement la mémoire lors du traitement
    de documents volumineux, évitant les fuites de mémoire.
    """

    tester = PipelineLoadTester()

    # Crée un contenu SFD très volumineux (~1 Mo) pour le test.
    large_sfd_content = "Spécification détaillée " * 50000

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(large_sfd_content)
        sfd_path = Path(f.name)

    orchestrator = Orchestrator()
    await orchestrator.initialize()

    try:
        # Exécute le pipeline avec le gros fichier SFD.
        result = await orchestrator.run_full_pipeline(str(sfd_path))

        assert result["status"] == "completed", "Le pipeline devrait se terminer avec succès."

        # Vérifie l'efficacité mémoire après le traitement.
        memory_metrics = tester.monitor_resources()
        # La limite de 20 Go est un exemple, à ajuster selon le modèle et les ressources.
        assert memory_metrics["memory_gb"] < 20, f"L'utilisation mémoire ({memory_metrics['memory_gb']:.2f} Go) devrait être inférieure à 20 Go."

    finally:
        await orchestrator.close()
        sfd_path.unlink(missing_ok=True)


@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_redis_operations(redis_client: redis.Redis):
    """Test la performance des opérations Redis sous forte concurrence."

    Vérifie que Redis peut gérer un grand nombre d'opérations de lecture/écriture
    concurrentes de manière efficace.
    """

    try:
        num_operations = 1000 # Nombre d'opérations de lecture/écriture à effectuer.

        write_tasks = []
        read_tasks = []

        start_time = time.time()

        # Exécute des opérations d'écriture concurrentes.
        for i in range(num_operations):
            task = redis_client.setex(f"perf_test_{i}", 60, f"data_{i}")
            write_tasks.append(task)

        await asyncio.gather(*write_tasks)
        write_time = time.time() - start_time
        logging.info(f"Temps pour {num_operations} écritures Redis : {write_time:.2f}s")

        # Exécute des opérations de lecture concurrentes.
        start_time = time.time()
        for i in range(num_operations):
            task = redis_client.get(f"perf_test_{i}")
            read_tasks.append(task)

        results = await asyncio.gather(*read_tasks)
        read_time = time.time() - start_time
        logging.info(f"Temps pour {num_operations} lectures Redis : {read_time:.2f}s")

        # Nettoyage des clés créées pendant le test.
        keys_to_delete = [f"perf_test_{i}" for i in range(num_operations)]
        if keys_to_delete:
            await redis_client.delete(*keys_to_delete)

        # Assertions sur les temps d'exécution et le nombre de succès.
        assert write_time < 5, f"Les {num_operations} écritures Redis devraient prendre moins de 5 secondes."
        assert read_time < 3, f"Les {num_operations} lectures Redis devraient prendre moins de 3 secondes."
        assert len([r for r in results if r is not None]) > 900, "Au moins 90% des lectures devraient réussir."

    finally:
        # S'assure que le client Redis est fermé.
        await redis_client.aclose()