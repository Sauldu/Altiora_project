# tests/integration/test_performance.py
"""
Tests de performance et charge du pipeline
"""

import pytest
import asyncio
import time
from src.orchestrator import Orchestrator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


@pytest.mark.performance
@pytest.mark.asyncio
async def test_pipeline_performance_metrics(tmp_path: Path):
    """Test les métriques de performance du pipeline."""

    # Générer 10 SFDs de différentes tailles
    sfd_contents = [
        f"Spécification {i}: Test de performance avec {i * 100} lignes de contenu " * 5
        for i in range(1, 11)
    ]

    results = []

    async def process_single_sfd(content, index):
        sfd_path = tmp_path / f"perf_{index}.txt"
        sfd_path.write_text(content)

        start_time = time.time()

        orchestrator = Orchestrator()
        await orchestrator.initialize()

        try:
            result = await orchestrator.process_sfd_to_tests(str(sfd_path))
            duration = time.time() - start_time

            return {
                "content_length": len(content),
                "duration": duration,
                "scenarios": result.get("metrics", {}).get("scenarios_found", 0),
                "tests": result.get("metrics", {}).get("tests_generated", 0)
            }
        finally:
            await orchestrator.close()

    # Exécution parallèle
    tasks = [process_single_sfd(content, i) for i, content in enumerate(sfd_contents)]
    results = await asyncio.gather(*tasks)

    # Analyse des résultats
    assert len(results) == 10

    avg_time = sum(r["duration"] for r in results) / len(results)
    assert avg_time < 300  # Moins de 5 minutes en moyenne

    # Vérifier la scalabilité
    for result in results:
        assert result["scenarios"] >= 1
        assert result["tests"] >= 1


@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_usage(tmp_path: Path):
    """Test la gestion de la mémoire avec de gros fichiers."""

    # Créer un gros SFD (simulation)
    large_content = "Contenu de test " * 1000  # ~20KB

    sfd_path = tmp_path / "large_sfd.txt"
    sfd_path.write_text(large_content)

    import psutil
    import os

    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss

    orchestrator = Orchestrator()
    await orchestrator.initialize()

    try:
        result = await orchestrator.process_sfd_to_tests(str(sfd_path))

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Vérifier que la mémoire ne dépasse pas 1GB
        assert memory_increase < 1_000_000_000  # 1GB
        assert result["status"] == "completed"

    finally:
        await orchestrator.close()