# services/alm/alm_service.py
"""Service web pour l'intégration avec un outil de gestion du cycle de vie des applications (ALM).

Ce service fournit des points de terminaison pour interagir avec un ALM externe
(comme Jira, Azure DevOps, etc.) afin de créer et gérer des éléments de travail.
Il est conçu pour être un pont générique, nécessitant une adaptation à l'API
spécifique de l'ALM cible.
"""

import logging
from typing import Dict, Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# --- Configuration --- #
class AlmSettings(BaseSettings):
    """Paramètres de configuration pour le service ALM.

    Ces paramètres sont chargés depuis les variables d'environnement ou un fichier .env.
    """
    alm_api_url: str = Field(..., description="URL de base de l'API de l'ALM cible.")
    alm_api_key: str = Field(..., description="Clé d'API pour l'authentification auprès de l'ALM.")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = AlmSettings()

# --- Modèles de Données --- #
class WorkItem(BaseModel):
    """Modèle Pydantic pour un élément de travail à créer dans l'ALM."""
    title: str = Field(..., description="Titre ou résumé de l'élément de travail.")
    description: str = Field(..., description="Description détaillée de l'élément de travail.")
    item_type: str = Field("Task", description="Type de l'élément de travail (ex: Task, Bug, User Story).")


# --- Initialisation de l'application FastAPI --- #
app = FastAPI(
    title="Service d'Intégration ALM",
    description="Un pont entre Altiora et un système de gestion de projet externe (ALM).",
    version="1.0.0",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Points de Terminaison (Endpoints) --- #
@app.get("/health", summary="Vérifie l'état de santé du service")
async def health_check() -> Dict[str, str]:
    """Point de terminaison pour la surveillance de base du service ALM."""
    return {"status": "ok"}


@app.post("/work-items", summary="Crée un nouvel élément de travail dans l'ALM")
async def create_work_item(item: WorkItem) -> Dict[str, Any]:
    """Crée un nouvel élément de travail (tâche, bug, etc.) dans le système ALM.
    
    Cette fonction est une maquette et doit être adaptée à l'API spécifique de votre ALM
    (ex: Jira, Azure DevOps). La logique actuelle simule une création réussie.

    Args:
        item: L'objet `WorkItem` contenant les détails de l'élément à créer.

    Returns:
        Un dictionnaire confirmant le succès et les détails de l'élément créé.

    Raises:
        HTTPException: Si une erreur survient lors de la communication avec l'ALM.
    """
    logger.info(f"Tentative de création d'un élément de travail de type '{item.item_type}' avec le titre : {item.title}")

    # --- Logique de maquette pour la démonstration --- #
    # Dans une implémentation réelle, cette section interagirait avec l'API de l'ALM.
    # Exemple de charge utile pour Jira:
    # payload = {
    #     "fields": {
    #         "project": {"key": "PROJ"},  # Clé du projet Jira
    #         "summary": item.title,
    #         "description": item.description,
    #         "issuetype": {"name": item.item_type},
    #     }
    # }
    # headers = {
    #     "Authorization": f"Bearer {settings.alm_api_key}",
    #     "Content-Type": "application/json",
    # }
    # async with httpx.AsyncClient() as client:
    #     response = await client.post(settings.alm_api_url, json=payload, headers=headers)
    #     response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP
    #     mock_response = response.json()
    logger.warning("L'appel à l'API ALM est actuellement une maquette. Adaptez `alm_service.py` pour votre ALM réel.")
    mock_response = {
        "id": "10001",
        "key": "PROJ-123",
        "self": f"{settings.alm_api_url}/rest/api/2/issue/10001", # URL simulée
    }
    # --- Fin de la logique de maquette --- #

    logger.info(f"Élément de travail créé avec succès (maquette) : {mock_response.get('key')}")
    return {"success": True, "work_item": mock_response}


# --- Pour un lancement direct (débogage/développement) --- #
if __name__ == "__main__":
    import uvicorn
    logger.info("Lancement du service ALM...")
    logger.info(f"URL de l'API ALM configurée : {settings.alm_api_url}")
    logger.info(f"Clé d'API ALM configurée : {'Oui' if settings.alm_api_key else 'Non'} (masquée)")
    uvicorn.run(app, host="0.0.0.0", port=8002)