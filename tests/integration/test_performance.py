# tests/integration/test_performance.py
"""Tests de performance et de charge pour le pipeline Altiora.

Ce module contient des tests d'intégration axés sur la performance,
mesurant le temps d'exécution et l'utilisation des ressources (mémoire)
du pipeline complet SFD → Tests Playwright sous différentes charges.
"""

import pytest
import asyncio
import time
from src.orchestrator import Orchestrator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any
import psutil
import os


@pytest.mark.performance
@pytest.mark.asyncio
async def test_pipeline_performance_metrics(tmp_path: Path):
    """Mesure les métriques de performance du pipeline SFD → Tests sur plusieurs documents."

    Ce test simule le traitement de plusieurs SFD de tailles différentes
    et collecte des métriques comme la durée d'exécution, le nombre de
    scénarios trouvés et de tests générés.
    """

    # Génère 10 SFD de différentes tailles pour simuler une charge variée.
    sfd_contents = [
        f"Spécification {i}: Test de performance avec {i * 100} lignes de contenu " * 5
        for i in range(1, 11)
    ]

    results = []

    async def process_single_sfd(content: str, index: int) -> Dict[str, Any]:
        """Fonction interne pour traiter une seule SFD et collecter ses métriques."

        Args:
            content: Le contenu textuel de la SFD.
            index: L'index du document (pour le nom de fichier).

        Returns:
            Un dictionnaire contenant la longueur du contenu, la durée de traitement,
            le nombre de scénarios et de tests générés.
        """
        sfd_path = tmp_path / f"perf_{index}.txt"
        sfd_path.write_text(content)

        start_time = time.time()

        orchestrator = Orchestrator() # Crée une nouvelle instance d'orchestrateur pour chaque SFD.
        await orchestrator.initialize()

        try:
            result = await orchestrator.run_full_pipeline(str(sfd_path)) # Utilise la méthode correcte.
            duration = time.time() - start_time

            return {
                "content_length": len(content),
                "duration": duration,
                "scenarios": result.get("metrics", {}).get("scenarios_found", 0),
                "tests": result.get("metrics", {}).get("tests_generated", 0)
            }
        finally:
            await orchestrator.close()

    # Exécute le traitement de chaque SFD en parallèle.
    tasks = [process_single_sfd(content, i) for i, content in enumerate(sfd_contents)]
    results = await asyncio.gather(*tasks)

    # Analyse et assertions sur les résultats agrégés.
    assert len(results) == 10, "Devrait avoir traité 10 SFD."

    avg_time = sum(r["duration"] for r in results) / len(results)
    # Assertion sur le temps moyen d'exécution (ajuster la valeur selon les performances attendues).
    assert avg_time < 300, f"Le temps moyen d'exécution ({avg_time:.2f}s) devrait être inférieur à 300 secondes."

    # Vérifie que des scénarios et des tests ont bien été générés pour chaque SFD.
    for result in results:
        assert result["scenarios"] >= 1, "Chaque SFD devrait générer au moins un scénario."
        assert result["tests"] >= 1, "Chaque SFD devrait générer au moins un test."


@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_usage(tmp_path: Path):
    """Test la gestion de la mémoire lors du traitement de gros fichiers SFD."

    Ce test vérifie que l'utilisation de la mémoire par le processus ne dépasse
    pas une certaine limite lors du traitement d'un grand document.
    """

    # Crée un contenu SFD volumineux pour simuler un gros fichier (~200KB).
    large_content = "Contenu de test pour un grand document SFD. " * 10000

    sfd_path = tmp_path / "large_sfd.txt"
    sfd_path.write_text(large_content)

    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss # Mémoire initiale du processus.

    orchestrator = Orchestrator()
    await orchestrator.initialize()

    try:
        result = await orchestrator.run_full_pipeline(str(sfd_path)) # Utilise la méthode correcte.

        final_memory = process.memory_info().rss # Mémoire finale du processus.
        memory_increase = final_memory - initial_memory

        # Vérifie que l'augmentation de la mémoire est inférieure à 1 Go (1_000_000_000 octets).
        assert memory_increase < 1_000_000_000, f"L'augmentation de la mémoire ({memory_increase / (1024**2):.2f} MB) devrait être inférieure à 1 Go."
        assert result["status"] == "completed", "Le pipeline devrait se terminer avec le statut 'completed'."

    finally:
        await orchestrator.close()
