"""
Tests fonctionnels pour les microservices de l'application Altiora.

Ce module contient des tests qui vérifient la fonctionnalité de base de
chaque microservice exposé via HTTP (ALM, Excel). Ces tests s'assurent
que les services répondent correctement aux requêtes et gèrent les cas
d'erreur, en se basant sur leurs endpoints de santé et leurs APIs spécifiques.
"""

import pytest
import httpx
import logging

logger = logging.getLogger(__name__)

# --- Configuration des clients de test ---
# Ces URLs ciblent les services qui devraient être en cours d'exécution.
# Assurez-vous que les services sont lancés avant d'exécuter ces tests.

BASE_URL_ALM = "http://localhost:8002"
BASE_URL_EXCEL = "http://localhost:8003"


@pytest.mark.service
@pytest.mark.asyncio
async def test_alm_service_health():
    """Vérifie que le service ALM est accessible et retourne un statut sain."

    Ce test envoie une requête GET à l'endpoint `/health` du service ALM
    et s'attend à une réponse HTTP 200 avec un statut "ok".
    """
    logger.info(f"Test de l'état de santé du service ALM à {BASE_URL_ALM}/health")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL_ALM}/health")
        response.raise_for_status() # Lève une exception pour les codes d'état HTTP 4xx/5xx.
        assert response.status_code == 200, f"Le service ALM devrait retourner un statut 200, mais a retourné {response.status_code}."
        assert response.json() == {"status": "ok"}, "Le corps de la réponse devrait être {'status': 'ok'}."


@pytest.mark.service
@pytest.mark.asyncio
async def test_alm_create_work_item_success():
    """Teste la création réussie d'un élément de travail via le service ALM."

    Ce test envoie une requête POST à l'endpoint `/work-items` avec des données
    valides et s'attend à une réponse de succès, vérifiant la structure de la réponse.
    """
    logger.info(f"Test de création d'un élément de travail via le service ALM à {BASE_URL_ALM}/work-items")
    payload = {
        "title": "Nouveau bug trouvé",
        "description": "Le bouton de connexion ne fonctionne pas sur Firefox.",
        "item_type": "Bug"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL_ALM}/work-items", json=payload)
        response.raise_for_status()
        assert response.status_code == 200, f"La création d'un élément de travail devrait retourner un statut 200, mais a retourné {response.status_code}."
        data = response.json()
        assert data["success"] is True, "Le champ 'success' devrait être True."
        assert "work_item" in data, "La réponse devrait contenir les détails de l'élément de travail."
        assert data["work_item"]["key"] == "PROJ-123", "La clé de l'élément de travail devrait correspondre à la maquette (PROJ-123)."


@pytest.mark.service
@pytest.mark.asyncio
async def test_alm_create_work_item_validation_error():
    """Teste la gestion d'une requête invalide par le service ALM."

    Ce test envoie une requête POST avec des données manquantes ou invalides
    et s'attend à une réponse HTTP 422 (Unprocessable Entity) indiquant une erreur de validation.
    """
    logger.info(f"Test de gestion d'erreur de validation par le service ALM à {BASE_URL_ALM}/work-items")
    payload = {"description": "Description sans titre"} # Le champ 'title' est requis et manquant.
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL_ALM}/work-items", json=payload)
        assert response.status_code == 422, f"Une requête invalide devrait retourner un statut 422, mais a retourné {response.status_code}."
        data = response.json()
        assert "detail" in data, "La réponse devrait contenir des détails sur l'erreur."
        assert any("field required" in str(err) for err in data["detail"]), "Le message d'erreur devrait indiquer un champ manquant."


@pytest.mark.service
@pytest.mark.asyncio
async def test_excel_service_health():
    """Vérifie que le service Excel est accessible et retourne un statut sain."

    Similaire au test de santé du service ALM, mais pour le service Excel.
    """
    logger.info(f"Test de l'état de santé du service Excel à {BASE_URL_EXCEL}/health")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL_EXCEL}/health")
        response.raise_for_status()
        assert response.status_code == 200, f"Le service Excel devrait retourner un statut 200, mais a retourné {response.status_code}."
        assert response.json() == {"status": "ok"}, "Le corps de la réponse devrait être {'status': 'ok'}."


@pytest.mark.service
@pytest.mark.asyncio
async def test_excel_create_matrix_success():
    """Teste la création réussie d'une matrice de test Excel."

    Ce test envoie des données de cas de test valides au service Excel et vérifie
    que le service retourne un fichier Excel non vide avec le bon type de contenu.
    """
    logger.info(f"Test de création d'une matrice Excel via le service Excel à {BASE_URL_EXCEL}/create-test-matrix")
    payload = {
        "filename": "test_matrix.xlsx",
        "test_cases": [
            {
                "id": "CU01_SB01_CP001_connexion_valide",
                "description": "Vérifier la connexion réussie.",
                "type": "CP"
            },
            {
                "id": "CU01_SB01_CE001_mot_de_passe_incorrect",
                "description": "Vérifier le message d'erreur.",
                "type": "CE"
            }
        ]
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(f"{BASE_URL_EXCEL}/create-test-matrix", json=payload)
        response.raise_for_status()
        assert response.status_code == 200, f"La création de la matrice Excel devrait retourner un statut 200, mais a retourné {response.status_code}."
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Le type de contenu devrait être un fichier Excel."
        assert len(response.content) > 0, "Le contenu du fichier Excel ne devrait pas être vide."


@pytest.mark.service
@pytest.mark.asyncio
async def test_excel_create_matrix_validation_error():
    """Teste la gestion de données invalides par le service Excel lors de la création d'une matrice."

    Ce test envoie des données de cas de test qui violent les règles de validation
    (ex: ID invalide) et s'attend à une réponse HTTP 400 (Bad Request) avec des détails sur l'erreur.
    """
    logger.info(f"Test de gestion d'erreur de validation par le service Excel à {BASE_URL_EXCEL}/create-test-matrix")
    payload = {
        "filename": "invalid_matrix.xlsx",
        "test_cases": [
            {
                "id": "ID_INVALIDE", # ID invalide selon la regex.
                "description": "Cet ID n'est pas valide.",
                "type": "CP"
            }
        ]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL_EXCEL}/create-test-matrix", json=payload)
        assert response.status_code == 400, f"Une requête avec des données invalides devrait retourner un statut 400, mais a retourné {response.status_code}."
        data = response.json()
        assert "detail" in data, "La réponse devrait contenir des détails sur l'erreur."
        assert "Les données des cas de test sont invalides" in data["detail"]["message"], "Le message d'erreur devrait indiquer une validation échouée."
        assert len(data["detail"]["errors"]) > 0, "La liste des erreurs de validation ne devrait pas être vide."