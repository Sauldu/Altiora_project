"""
Tests fonctionnels pour les microservices de l'application Altiora.
"""

import pytest
import httpx

# --- Configuration des clients de test ---
# Ces clients ciblent les services qui devraient être en cours d'exécution.
# Assurez-vous que les services sont lancés avant d'exécuter ces tests.

BASE_URL_ALM = "http://localhost:8002"
BASE_URL_EXCEL = "http://localhost:8003"


@pytest.mark.service
@pytest.mark.asyncio
async def test_alm_service_health():
    """Vérifie que le service ALM est accessible."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL_ALM}/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.service
@pytest.mark.asyncio
async def test_alm_create_work_item_success():
    """Teste la création réussie d'un élément de travail via le service ALM."""
    payload = {
        "title": "Nouveau bug trouvé",
        "description": "Le bouton de connexion ne fonctionne pas sur Firefox.",
        "item_type": "Bug"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL_ALM}/work-items", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "work_item" in data
        assert data["work_item"]["key"] == "PROJ-123" # Basé sur la maquette


@pytest.mark.service
@pytest.mark.asyncio
async def test_alm_create_work_item_validation_error():
    """Teste la gestion d'une requête invalide par le service ALM."""
    payload = {"description": "Description sans titre"} # Titre manquant
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL_ALM}/work-items", json=payload)
        assert response.status_code == 422  # Unprocessable Entity


@pytest.mark.service
@pytest.mark.asyncio
async def test_excel_service_health():
    """Vérifie que le service Excel est accessible."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL_EXCEL}/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.service
@pytest.mark.asyncio
async def test_excel_create_matrix_success():
    """Teste la création réussie d'une matrice de test Excel."""
    payload = {
        "filename": "test_matrix.xlsx",
        "test_cases": [
            {
                "id": "CU01_SB01_CP001_connexion_valide",
                "description": "Vérifier la connexion réussie.",
                "type": "CP"
            }
        ]
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(f"{BASE_URL_EXCEL}/create-test-matrix", json=payload)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        # Vérifier que le contenu n'est pas vide
        assert len(response.content) > 0


@pytest.mark.service
@pytest.mark.asyncio
async def test_excel_create_matrix_validation_error():
    """Teste la gestion de données invalides par le service Excel."""
    payload = {
        "filename": "invalid_matrix.xlsx",
        "test_cases": [
            {
                "id": "ID_INVALIDE",
                "description": "Cet ID n'est pas valide.",
                "type": "CP"
            }
        ]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL_EXCEL}/create-test-matrix", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "Les données des cas de test sont invalides" in data["detail"]["message"]
        assert len(data["detail"]["errors"]) > 0
