# tests/integration/test_services_integration.py
"""Tests d'intégration entre les différents microservices d'Altiora.

Ce module contient des tests qui vérifient la bonne communication et le
fonctionnement conjoint des services (OCR, Qwen3, StarCoder2, Excel, ALM,
Playwright). Ces tests simulent des flux de travail complexes pour s'assurer
de l'interopérabilité des composants.
"""

import pytest
import asyncio
import aiohttp
import json
import tempfile
from pathlib import Path


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ocr_to_qwen3_to_starcoder2_flow(wait_for_services):
    """Test le flux d'intégration complet : OCR → Qwen3 → StarCoder2."

    Ce test simule le processus d'analyse d'une SFD (via OCR), son traitement
    par Qwen3 pour extraire les scénarios, puis la génération de code de test
    par StarCoder2 à partir de ces scénarios.
    """
    # 1. Préparation d'un fichier SFD temporaire.
    sfd_content = "Test de connexion avec email et mot de passe. Scénario: Connexion réussie."
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(sfd_content)
        sfd_path = Path(f.name)

    try:
        async with aiohttp.ClientSession() as session:
            # 2. Appel au service OCR pour extraire le texte.
            # Note: Le service OCR est mocké ou utilise une implémentation simple pour les tests.
            ocr_payload = {
                "file_path": str(sfd_path),
                "language": "fra",
                "preprocess": False,
                "cache": False
            }
            async with session.post("http://localhost:8001/extract", json=ocr_payload) as resp:
                resp.raise_for_status()
                ocr_result = await resp.json()
                assert "text" in ocr_result
                extracted_text = ocr_result["text"]

            # 3. Appel au modèle Qwen3 pour l'analyse SFD.
            qwen3_payload = {
                "model": "qwen3-sfd-analyzer",
                "prompt": f"Analyze the following SFD and extract test scenarios in JSON format: {extracted_text}",
                "stream": False,
                "options": {"num_predict": 500, "temperature": 0.1}
            }
            async with session.post("http://localhost:11434/api/generate", json=qwen3_payload) as resp:
                resp.raise_for_status()
                qwen3_raw_response = await resp.json()
                # Extrait la partie JSON de la réponse de Qwen3.
                qwen3_response_text = qwen3_raw_response.get("response", "{}")
                try:
                    qwen3_parsed_response = json.loads(qwen3_response_text)
                except json.JSONDecodeError:
                    pytest.fail(f"La réponse de Qwen3 n'est pas un JSON valide : {qwen3_response_text}")
                
                assert "scenarios" in qwen3_parsed_response, "La réponse de Qwen3 devrait contenir des scénarios."
                assert len(qwen3_parsed_response["scenarios"]) > 0, "Qwen3 devrait extraire au moins un scénario."
                scenario_for_starcoder = qwen3_parsed_response["scenarios"][0]

            # 4. Appel au modèle StarCoder2 pour la génération de code de test.
            starcoder2_payload = {
                "model": "starcoder2-playwright",
                "prompt": f"Generate a Playwright test in Python for the following scenario: {json.dumps(scenario_for_starcoder)}",
                "stream": False,
                "options": {"num_predict": 500, "temperature": 0.1}
            }
            async with session.post("http://localhost:11434/api/generate", json=starcoder2_payload) as resp:
                resp.raise_for_status()
                starcoder2_raw_response = await resp.json()
                generated_code = starcoder2_raw_response.get("response", "")

                assert "def test_" in generated_code, "Le code généré par StarCoder2 devrait contenir une fonction de test."
                assert "page.goto" in generated_code, "Le code généré devrait contenir une navigation Playwright."

    finally:
        sfd_path.unlink(missing_ok=True)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_excel_alm_integration(wait_for_services):
    """Test le flux d'intégration : Génération Excel → Importation ALM."

    Ce test vérifie que le service Excel peut générer une matrice de test
    et que le service ALM peut ensuite importer ces données (simulées).
    """

    test_data_for_excel = [
        {
            "id": "CU01_SB01_CP001_login_success",
            "description": "Test connexion réussie",
            "type": "CP",
        },
        {
            "id": "CU01_SB01_CE001_invalid_login",
            "description": "Test échec de connexion",
            "type": "CE",
        }
    ]

    async with aiohttp.ClientSession() as session:
        # 1. Appel au service Excel pour créer une matrice de tests.
        excel_payload = {
            "filename": "integration_test_matrix.xlsx",
            "test_cases": test_data_for_excel
        }
        async with session.post("http://localhost:8003/create-test-matrix", json=excel_payload) as resp:
            resp.raise_for_status()
            excel_response_content = await resp.read() # Le service Excel retourne le fichier binaire.
            assert len(excel_response_content) > 0, "Le service Excel devrait retourner un fichier non vide."

        # 2. Appel au service ALM pour importer un élément de travail (simulé).
        # Note: Le service ALM est mocké pour les tests d'intégration.
        alm_payload = {
            "title": "Import de cas de test depuis Excel",
            "description": "Cas de test générés automatiquement et importés via le service Excel.",
            "item_type": "Task"
        }
        async with session.post("http://localhost:8002/work-items", json=alm_payload) as resp:
            resp.raise_for_status()
            alm_result = await resp.json()
            assert alm_result["success"] is True, "L'importation ALM devrait réussir."
            assert "work_item" in alm_result, "Le résultat ALM devrait contenir les détails de l'élément de travail."


@pytest.mark.integration
@pytest.mark.asyncio
async def test_playwright_execution(wait_for_services):
    """Test l'exécution réelle de tests Playwright via le service dédié."

    Ce test envoie un script Playwright simple au service `playwright_runner`
    et vérifie que l'exécution se déroule correctement.
    """

    test_code_to_execute = '''
import pytest
from playwright.async_api import Page, expect

@pytest.mark.asyncio
async def test_example_page_load(page: Page):
    """Un test simple pour charger une page et vérifier son titre."""
    await page.goto("https://www.google.com")
    await expect(page).to_have_title(/Google/)
'''

    playwright_payload = {
        "tests": [{"code": test_code_to_execute, "test_name": "test_google_load"}],
        "config": {
            "browser": "chromium",
            "headed": False, # Exécution en mode headless.
            "timeout": 30000
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("http://localhost:8004/execute", json=playwright_payload) as resp:
            resp.raise_for_status()
            result = await resp.json()
            assert result["status"] == "completed", f"L'exécution Playwright devrait être complétée, mais est {result.get('status')}. Erreur: {result.get('error')}"
            assert result["passed"] == 1, "Le test Playwright devrait réussir."
            assert result["failed"] == 0, "Aucun test Playwright ne devrait échouer."
            assert len(result["results"]) == 1, "Un seul résultat de test devrait être retourné."
            assert result["results"][0]["status"] == "passed", "Le statut du test individuel devrait être 'passed'."
