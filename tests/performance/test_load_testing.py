# tests/performance/test_load_testing.py
"""
Tests de charge CPU pour Altiora
Optimisés pour Intel i5-13500H (14 cores, 32GB RAM)
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List

import aiohttp
import psutil
import pytest

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Métriques de performance CPU"""
    cpu_usage: List[float]
    memory_usage: List[float]
    response_times: List[float]
    throughput: float
    error_rate: float
    concurrent_requests: int


class CPULoadTester:
    """Testeur de charge CPU spécialisé pour Altiora"""

    def __init__(self, target_cpu: int = 80, max_memory_gb: float = 28.0):
        self.target_cpu = target_cpu
        self.max_memory_gb = max_memory_gb
        self.cpu_cores = psutil.cpu_count(logical=False)
        self.p_cores = 6  # Performance cores i5-13500H
        self.e_cores = 8  # Efficiency cores i5-13500H

    def get_system_metrics(self) -> Dict[str, Any]:
        """Récupère les métriques système actuelles"""
        cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
        memory = psutil.virtual_memory()

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_gb": memory.used / (1024 ** 3),
            "temperature": self._get_cpu_temperature(),
            "load_average": psutil.getloadavg()
        }

    @staticmethod
    def _get_cpu_temperature() -> float:
        """Récupère la température CPU (Linux)"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return float(f.read().strip()) / 1000
        except (IOError, OSError) as e:
            logger.warning(f"Could not read CPU temperature: {e}")
            return 0.0

    @staticmethod
    async def stress_test_qwen3(num_concurrent: int = 10):
        """Test de charge sur Qwen3 avec analyses parallèles"""

        test_payloads = [
            f"Analyse ce scénario de test {i}: connexion utilisateur avec validation email"
            for i in range(num_concurrent)
        ]

        metrics = {
            "start_time": time.time(),
            "total_requests": num_concurrent,
            "successful": 0,
            "failed": 0,
            "response_times": []
        }

        async def single_request(payload: str):
            async with aiohttp.ClientSession() as session:
                start = time.time()
                try:
                    async with session.post(
                            "http://localhost:11434/api/generate",
                            json={
                                "model": "qwen3:32b-q4_K_M",
                                "prompt": payload,
                                "stream": False,
                                "options": {
                                    "num_ctx": 8192,
                                    "num_predict": 512,
                                    "temperature": 0.7
                                }
                            },
                            timeout=aiohttp.ClientTimeout(total=300)
                    ) as resp:
                        duration = time.time() - start
                        if resp.status == 200:
                            metrics["successful"] += 1
                        else:
                            metrics["failed"] += 1
                        metrics["response_times"].append(duration)
                        return duration
                except Exception as e:
                    metrics["failed"] += 1
                    logger.error(f"Erreur requête: {e}")
                    return 0

        # Exécution parallèle
        tasks = [single_request(payload) for payload in test_payloads]
        await asyncio.gather(*tasks)

        metrics["total_time"] = time.time() - metrics["start_time"]
        metrics["throughput"] = metrics["successful"] / metrics["total_time"]

        return metrics

    @staticmethod
    async def memory_stress_test(data_size_mb: int = 100):
        """Test de stress mémoire avec gros volumes de données"""

        # Générer des données volumineuses
        large_sfd = "Contenu de spécification " * 10000  # ~200KB

        # Créer 100 fichiers de test
        test_files = []
        for i in range(100):
            file_path = Path(f"/tmp/large_sfd_{i}.txt")
            file_path.write_text(large_sfd * 50)  # ~10MB par fichier
            test_files.append(file_path)

        metrics = {
            "files_processed": 0,
            "total_size_mb": 0,
            "peak_memory_mb": 0,
            "processing_times": []
        }

        # Monitorer la mémoire
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 ** 3)

        for file_path in test_files[:10]:  # Limiter pour les tests
            start_time = time.time()
            start_memory = process.memory_info().rss / (1024 ** 3)

            # Simuler le traitement
            content = file_path.read_text()
            metrics["total_size_mb"] += len(content) / (1024 ** 2)

            # Libération mémoire
            del content

            end_memory = process.memory_info().rss / (1024 ** 3)
            metrics["peak_memory_mb"] = max(metrics["peak_memory_mb"], end_memory)
            metrics["processing_times"].append(time.time() - start_time)
            metrics["files_processed"] += 1

            file_path.unlink()

        metrics["memory_increase_gb"] = metrics["peak_memory_mb"] - initial_memory
        metrics["memory_efficiency"] = metrics["total_size_mb"] / metrics["memory_increase_gb"]

        return metrics

    @staticmethod
    async def concurrent_playwright_tests(num_tests: int = 50):
        """Test avec génération parallèle de tests Playwright"""

        test_scenarios = [
            {
                "titre": f"Test {i}",
                "description": f"Test de connexion {i}",
                "etapes": ["Naviguer", "Saisir", "Valider"]
            }
            for i in range(num_tests)
        ]

        metrics = {
            "tests_generated": 0,
            "total_time": 0,
            "avg_generation_time": 0,
            "memory_usage": []
        }

        start_time = time.time()

        async def generate_single_test(scenario: dict):
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                            "http://localhost:11434/api/generate",
                            json={
                                "model": "starcoder2:15b-q8_0",
                                "prompt": f"Generate Playwright test for: {scenario['titre']}",
                                "stream": False,
                                "options": {"num_predict": 1000}
                            },
                            timeout=300
                    ) as resp:
                        if resp.status == 200:
                            return await resp.json()
                except Exception as e:
                    logger.error(f"Erreur génération test: {e}")
                    return None

        # Exécution par lots pour éviter la surcharge
        batch_size = min(10, num_tests)
        for i in range(0, num_tests, batch_size):
            batch = test_scenarios[i:i + batch_size]
            tasks = [generate_single_test(scenario) for scenario in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            metrics["tests_generated"] += sum(1 for r in results if r and not isinstance(r, Exception))

            # Pause pour laisser respirer le CPU
            await asyncio.sleep(1)

        metrics["total_time"] = time.time() - start_time
        metrics["avg_generation_time"] = metrics["total_time"] / metrics["tests_generated"]

        return metrics


@pytest.mark.performance
@pytest.mark.asyncio
async def test_cpu_load_80_percent():
    """Test de charge à 80% CPU"""

    tester = CPULoadTester(target_cpu=80)

    # Test Qwen3 sous charge
    metrics = await tester.stress_test_qwen3(num_concurrent=15)

    assert metrics["successful"] >= 12  # 80% de succès
    assert metrics["throughput"] > 0.5  # Au moins 0.5 req/sec

    # Vérifier que le CPU ne dépasse pas 90%
    cpu_percent = psutil.cpu_percent(interval=5)
    assert cpu_percent < 90, f"CPU trop élevé: {cpu_percent}%"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_efficiency():
    """Test d'efficacité mémoire"""

    tester = CPULoadTester()

    metrics = await tester.memory_stress_test(data_size_mb=50)

    # Ratio d'efficacité mémoire
    assert metrics["memory_efficiency"] > 0.8  # 80% d'efficacité
    assert metrics["memory_increase_gb"] < 2  # Moins de 2GB d'augmentation


@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_test_generation():
    """Test de génération parallèle de tests"""

    tester = CPULoadTester()

    metrics = await tester.concurrent_playwright_tests(num_tests=20)

    assert metrics["tests_generated"] >= 18  # 90% de succès
    assert metrics["avg_generation_time"] < 30  # Moins de 30s par test


@pytest.mark.performance
@pytest.mark.asyncio
async def test_error_handling():
    """Test de gestion des erreurs"""

    tester = CPULoadTester()

    # Simuler une erreur de connexion
    async def failing_request():
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                        "http://localhost:11434/api/generate",
                        json={"model": "invalid_model", "prompt": "Test"},
                        timeout=300
                ) as resp:
                    return await resp.json()
            except Exception as e:
                logger.error(f"Erreur requête: {e}")
                return None

    result = await failing_request()

    assert result is None  # Vérifier que l'erreur est gérée correctement
