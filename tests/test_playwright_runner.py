# tests/test_playwright_runner.py
"""Tests unitaires pour le service d'exécution de tests Playwright (`playwright_runner.py`).

Ce module contient des tests pour vérifier les fonctionnalités clés du runner
Playwright, telles que la préparation des fichiers de test, la génération de
la configuration Pytest, et l'exécution des tests.
"""

import pytest
import asyncio
from pathlib import Path
from typing import Dict, Any

# Importe les fonctions et classes du module playwright_runner.
from services.playwright.playwright_runner import prepare_test_files, generate_pytest_config, TestCode, ExecutionConfig


@pytest.fixture
def test_scenario_data() -> Dict[str, Any]:
    """Fixture fournissant des données de scénario de test Playwright factices."""
    return {
        "code": "await page.goto('https://example.com')\nawait expect(page).to_have_title('Example')",
        "test_name": "test_navigation_example",
        "test_type": "e2e"
    }


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Fixture fournissant un répertoire de travail temporaire pour les tests."

    Args:
        tmp_path: Fixture Pytest pour un répertoire temporaire.

    Returns:
        Le chemin vers le répertoire de travail temporaire.
    """
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    return workspace_dir


@pytest.mark.asyncio
async def test_prepare_test_files(temp_workspace: Path, test_scenario_data: Dict[str, Any]):
    """Teste la préparation des fichiers de test à partir des données de scénario."

    Vérifie que les fichiers `.py` sont créés correctement dans le répertoire
    temporaire et qu'ils contiennent le code de test.
    """
    # Crée un objet TestCode à partir des données de la fixture.
    test_code_obj = TestCode(**test_scenario_data)

    # Appelle la fonction à tester.
    test_files = await prepare_test_files([test_code_obj], temp_workspace)

    # Assertions.
    assert len(test_files) == 1, "Un seul fichier de test devrait être créé."
    created_file = test_files[0]
    assert created_file.exists(), "Le fichier de test devrait exister."
    assert created_file.suffix == ".py", "Le fichier devrait avoir l'extension .py."
    assert test_code_obj.test_name in created_file.name, "Le nom du fichier devrait contenir le nom du test."

    # Vérifie le contenu du fichier.
    content = created_file.read_text()
    assert "import pytest" in content, "Le fichier devrait contenir l'import pytest."
    assert "from playwright.async_api import Page, expect" in content, "Le fichier devrait contenir les imports Playwright."
    assert test_code_obj.code in content, "Le fichier devrait contenir le code du scénario."
    assert "@pytest.mark.asyncio" in content, "Le test asynchrone devrait être décoré avec @pytest.mark.asyncio."

    # Vérifie que conftest.py est créé.
    conftest_path = temp_workspace / "conftest.py"
    assert conftest_path.exists(), "Le fichier conftest.py devrait être créé."


def test_generate_pytest_config():
    """Teste la génération des arguments de ligne de commande pour Pytest."

    Vérifie que les arguments générés reflètent correctement la configuration
    d'exécution fournie.
    """
    # Crée un objet ExecutionConfig avec différentes options.
    config = ExecutionConfig(
        browser="firefox",
        headed=True,
        timeout=60000, # 60 secondes.
        retries=1,
        parallel=True,
        workers=3,
        screenshot="on-failure",
        video="always",
        trace="on-failure",
        base_url="https://my-app.com"
    )

    # Appelle la fonction à tester.
    pytest_args = generate_pytest_config(config, Path("/test_workspace"))

    # Assertions sur les arguments générés.
    assert "-v" in pytest_args, "Le mode verbeux devrait être activé."
    assert "--tb=short" in pytest_args, "Le format de traceback courte devrait être activé."
    assert "--json-report" in pytest_args, "Le rapport JSON devrait être activé."
    assert "--browser=firefox" in pytest_args, "Le navigateur Firefox devrait être spécifié."
    assert "--headed" in pytest_args, "Le mode 'headed' devrait être activé."
    assert "-n" in pytest_args, "L'option de parallélisation (-n) devrait être présente."
    assert "3" in pytest_args, "Le nombre de workers devrait être 3."
    assert "--screenshot=only-on-failure" in pytest_args, "La capture d'écran sur échec devrait être configurée."
    assert "--video=on" in pytest_args, "L'enregistrement vidéo devrait être activé."
    assert "--tracing=retain-on-failure" in pytest_args, "Le traçage sur échec devrait être configuré."
    assert "--timeout=60" in pytest_args, "Le timeout devrait être de 60 secondes."

    # Vérifie que les arguments spécifiques au workspace sont présents.
    assert str(Path("/test_workspace")) in pytest_args, "Le chemin du workspace devrait être inclus."
    assert f"--json-report-file={Path("/test_workspace") / 'report.json'}" in pytest_args, "Le chemin du rapport JSON devrait être correct."
