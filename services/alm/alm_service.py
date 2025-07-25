"""
Service web pour l'intégration avec un outil de gestion du cycle de vie des applications (ALM).

Ce service fournit des points de terminaison pour interagir avec un ALM externe
(comme Jira, Azure DevOps, etc.) afin de créer et gérer des éléments de travail.
"""

import logging
from typing import Dict, Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from src.models.starcoder2.starcoder2_interface import StarCoder2OllamaInterface
# --- Configuration ---
class AlmSettings(BaseSettings):
    alm_api_url: str = Field(..., description="URL de base de l'API de l'ALM.")
    alm_api_key: str = Field(..., description="Clé d'API pour l'authentification auprès de l'ALM.")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = AlmSettings()

# --- Modèles de Données ---
class WorkItem(BaseModel):
    title: str
    description: str
    item_type: str = "Task"  # Ex: Task, Bug, User Story


# --- Initialisation de l'application ---
app = FastAPI(
    title="Service d'Intégration ALM",
    description="Un pont entre Altiora et un système de gestion de projet externe.",
    version="1.0.0",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Points de Terminaison ---
@app.get("/health", summary="Vérifie l'état de santé du service")
async def health_check() -> Dict[str, str]:
    """Point de terminaison pour la surveillance de base."""
    return {"status": "ok"}


@app.post("/work-items", summary="Crée un nouvel élément de travail dans l'ALM")
async def create_work_item(item: WorkItem) -> Dict[str, Any]:
    """
    Crée un nouvel élément de travail (tâche, bug, etc.) dans le système ALM.
    
    Cette fonction est une maquette et doit être adaptée à l'API spécifique de votre ALM.
    """
    logger.info(f"Tentative de création d'un élément de travail de type '{item.item_type}' avec le titre : {item.title}")

    # Adapter cette charge utile à la structure attendue par votre API ALM
    payload = {
        "fields": {
            "project": {"key": "PROJ"},  # À adapter
            "summary": item.title,
            "description": item.description,
            "issuetype": {"name": item.item_type},
        }
    }

    headers = {
        "Authorization": f"Bearer {settings.alm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            # La ligne suivante est commentée car elle nécessite une véritable API ALM.
            # response = await client.post(settings.alm_api_url, json=payload, headers=headers)
            # response.raise_for_status()
            
            # --- Maquette de réponse pour la démonstration ---
            logger.warning("L'appel à l'API ALM est actuellement une maquette.")
            mock_response = {
                "id": "10001",
                "key": "PROJ-123",
                "self": f"{settings.alm_api_url}/rest/api/2/issue/10001",
            }
            # --- Fin de la maquette ---

        logger.info(f"Élément de travail créé avec succès : {mock_response.get('key')}")
        return {"success": True, "work_item": mock_response}

    except httpx.HTTPStatusError as e:
        logger.error(f"Erreur de l'API ALM : {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Erreur de l'API ALM : {e.response.text}",
        )
    except Exception as e:
        logger.error(f"Erreur interne lors de la communication avec l'ALM : {e}")
        raise HTTPException(
            status_code=500, detail="Erreur interne du service ALM."
        )


# --- Pour un lancement direct (débogage) ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Lancement du service ALM sur http://localhost:8002")
    logger.info(f"URL de l'API ALM configurée : {settings.alm_api_url}")
    logger.info(f"Clé d'API ALM configurée : {'Oui' if settings.alm_api_key else 'Non'}")
    uvicorn.run(app, host="0.0.0.0", port=8002)
