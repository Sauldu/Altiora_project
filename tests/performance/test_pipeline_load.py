# tests/performance/test_pipeline_load.py
"""
Tests de charge complets pour le pipeline Altiora
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

import psutil
import pytest

from src.orchestrator import Orchestrator


class PipelineLoadTester:
    """Testeur de charge pour le pipeline complet"""

    def __init__(self):
        self.cpu_limit = 85  # 85% CPU max
        self.memory_limit = 25  # 25GB max
        self.process = psutil.Process()

    def monitor_resources(self) -> Dict[str, float]:
        """Surveillance des ressources système"""
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
        """Récupère la température CPU"""
        try:
            temps = psutil.sensors_temperatures()
            if 'coretemp' in temps:
                return max([t.current for t in temps['coretemp']])
            return 0.0
        except:
            return 0.0

    def should_stop_load(self) -> bool:
        """Détermine si on doit arrêter la charge"""
        metrics = self.monitor_resources()
        return (
                metrics["cpu_percent"] > self.cpu_limit or
                metrics["memory_gb"] > self.memory_limit or
                metrics["temperature"] > 80
        )

    async def load_test_full_pipeline(self, num_concurrent: int = 20):
        """Test de charge complet du pipeline"""

        # Créer des SFDs de test
        sfd_templates = [
            "Spécification login: email, password, validation",
            "Spécification API: endpoints, méthodes, authentification",
            "Spécification UI: formulaires, boutons, validations"
        ]

        results = []
        orchestrator = Orchestrator()
        await orchestrator.initialize()

        try:
            # Test parallèle
            tasks = []
            for i in range(num_concurrent):
                sfd_content = f"{sfd_templates[i % len(sfd_templates)]} - test {i}"
                task = self._single_pipeline_test(orchestrator, sfd_content, i)
                tasks.append(task)

            # Exécution avec limitation de charge
            batch_size = 5
            for i in range(0, num_concurrent, batch_size):
                if self.should_stop_load():
                    logger.warning("Arrêt de la charge due aux limites système")
                    break

                batch = tasks[i:i + batch_size]
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                results.extend(batch_results)

                # Pause pour laisser respirer le système
                await asyncio.sleep(2)

        finally:
            await orchestrator.close()

        return self._analyze_results(results)

    async def _single_pipeline_test(self, orchestrator: Orchestrator, sfd_content: str, index: int) -> Dict:
        """Test unique du pipeline"""

        start_time = time.time()
        start_resources = self.monitor_resources()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(sfd_content)
            sfd_path = f.name

        try:
            result = await orchestrator.process_sfd_to_tests(sfd_path)

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
            Path(sfd_path).unlink()

    @staticmethod
    def _analyze_results(results: List[Dict]) -> Dict[str, Any]:
        """Analyse des résultats de charge"""

        successful = [r for r in results if r.get("success", False)]
        failed = [r for r in results if not r.get("success", False)]

        if successful:
            avg_duration = sum(r["duration"] for r in successful) / len(successful)
            avg_scenarios = sum(r["scenarios"] for r in successful) / len(successful)
            avg_tests = sum(r["tests_generated"] for r in successful) / len(successful)
        else:
            avg_duration = avg_scenarios = avg_tests = 0

        return {
            "total_tests": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(results) * 100,
            "avg_duration": avg_duration,
            "avg_scenarios": avg_scenarios,
            "avg_tests": avg_tests,
            "throughput": len(successful) / max([r["duration"] for r in successful], default=1),
            "error_rate": len(failed) / len(results) * 100
        }


@pytest.mark.performance
@pytest.mark.asyncio
async def test_cpu_load_pipeline():
    """Test de charge CPU avec pipeline complet"""

    tester = PipelineLoadTester()

    # Configurer les limites pour le test
    metrics = await tester.load_test_full_pipeline(num_concurrent=10)

    assert metrics["success_rate"] > 80  # 80% de succès
    assert metrics["avg_duration"] < 120  # Moins de 2 minutes par test
    assert metrics["throughput"] > 0.1  # Au moins 0.1 test/seconde

    # Vérification des ressources
    final_metrics = tester.monitor_resources()
    assert final_metrics["cpu_percent"] < 90
    assert final_metrics["memory_gb"] < 25


@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_efficiency_pipeline():
    """Test d'efficacité mémoire du pipeline"""

    tester = PipelineLoadTester()

    # Test avec volume contrôlé
    large_sfd = "Spécification détaillée " * 5000  # ~100KB

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(large_sfd)
        sfd_path = f.name

    try:
        orchestrator = Orchestrator()
        await orchestrator.initialize()

        # Monitorer la mémoire pendant le traitement
        monitor_task = asyncio.create_task(tester._monitor_memory_continuous())

        result = await orchestrator.process_sfd_to_tests(sfd_path)

        monitor_task.cancel()

        assert result["status"] == "completed"

        # Vérifier l'efficacité mémoire
        memory_metrics = tester.monitor_resources()
        assert memory_metrics["memory_gb"] < 20  # Moins de 20GB utilisés

    finally:
        await orchestrator.close()
        Path(sfd_path).unlink()


@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_redis_operations():
    """Test des opérations Redis concurrentes"""

    client = await redis.from_url("redis://localhost:6379", decode_responses=True)

    try:
        # Test écriture/lecture concurrente
        num_operations = 1000

        write_tasks = []
        read_tasks = []

        start_time = time.time()

        # Écriture concurrente
        for i in range(num_operations):
            task = client.setex(f"perf_test_{i}", 60, f"data_{i}")
            write_tasks.append(task)

        await asyncio.gather(*write_tasks)
        write_time = time.time() - start_time

        # Lecture concurrente
        start_time = time.time()
        for i in range(num_operations):
            task = client.get(f"perf_test_{i}")
            read_tasks.append(task)

        results = await asyncio.gather(*read_tasks)
        read_time = time.time() - start_time

        # Nettoyage
        keys = await client.keys("perf_test_*")
        if keys:
            await client.delete(*keys)

        # Assertions
        assert write_time < 5  # Moins de 5 secondes pour 1000 écritures
        assert read_time < 3  # Moins de 3 secondes pour 1000 lectures
        assert len([r for r in results if r is not None]) > 900

    finally:
        await client.aclose()
