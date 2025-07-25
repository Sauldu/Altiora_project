# services/excel/excel_service.py
"""Service web pour la création et la manipulation de fichiers Excel.

Ce service expose une API pour générer des fichiers Excel stylisés,
notamment des matrices de test, en s'appuyant sur les modules de politique
et de formatage internes (`policies.excel_policy`, `post_processing.excel_formatter`).
"""

import logging
import os
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Importation des modules internes pour la validation et le formatage.
from policies.excel_policy import ExcelPolicy
from post_processing.excel_formatter import ExcelFormatter

# --- Modèles de Données --- #
class TestCase(BaseModel):
    """Modèle Pydantic pour un cas de test individuel."""
    id: str = Field(..., description="L'identifiant unique du cas de test.")
    description: str = Field(..., description="La description détaillée du cas de test.")
    type: str = Field(..., description="Le type de cas de test (ex: CP pour Cas Passant, CE pour Cas d'Erreur, CL pour Cas Limite).")


class TestMatrixRequest(BaseModel):
    """Modèle Pydantic pour une requête de création de matrice de tests Excel."""
    filename: str = Field(default="matrice_de_test.xlsx", description="Le nom du fichier Excel à générer.")
    test_cases: List[TestCase] = Field(..., description="Liste des cas de test à inclure dans la matrice.")


# --- Initialisation de l'application FastAPI --- #
app = FastAPI(
    title="Service de Génération Excel",
    description="Crée des fichiers Excel stylisés à partir de données structurées.",
    version="1.0.0",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Répertoire temporaire pour stocker les rapports Excel générés.
OUTPUT_DIR = "temp_excel_reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialisation des classes de politique et de formatage.
policy = ExcelPolicy()
formatter = ExcelFormatter()


# --- Points de Terminaison (Endpoints) --- #
@app.get("/health", summary="Vérifie l'état de santé du service")
async def health_check() -> Dict[str, str]:
    """Point de terminaison pour la surveillance de base du service Excel."""
    return {"status": "ok"}


@app.post("/create-test-matrix", summary="Crée un fichier Excel de matrice de tests")
async def create_test_matrix(request: TestMatrixRequest, background_tasks: BackgroundTasks) -> FileResponse:
    """Génère un fichier Excel à partir d'une liste de cas de test fournie.
    
    Les données sont d'abord validées par `ExcelPolicy`, puis formatées par `ExcelFormatter`.
    Le fichier généré est ensuite envoyé en réponse et supprimé en arrière-plan.

    Args:
        request: L'objet `TestMatrixRequest` contenant le nom du fichier et les cas de test.
        background_tasks: Tâches de fond FastAPI pour la suppression du fichier temporaire.

    Returns:
        Une `FileResponse` contenant le fichier Excel généré.

    Raises:
        HTTPException: Si la validation des données échoue ou si une erreur survient lors de la génération du fichier.
    """
    logger.info(f"Requête reçue pour créer la matrice de tests : {request.filename}")

    # Convertit les modèles Pydantic en dictionnaires Python standard pour les modules de politique et de formatage.
    test_cases_data = [case.model_dump() for case in request.test_cases]

    # 1. Valide les données des cas de test en utilisant la politique définie.
    validation_result = policy.validate_test_matrix(test_cases_data)
    if not validation_result["is_valid"]:
        logger.error(f"Validation des données échouée : {validation_result['errors']}")
        raise HTTPException(
            status_code=400,
            detail={"message": "Les données des cas de test sont invalides.", "errors": validation_result["errors"]}
        )

    # 2. Formate et génère le fichier Excel.
    output_path = os.path.join(OUTPUT_DIR, request.filename)
    try:
        formatting_errors = formatter.format_test_matrix(test_cases_data, output_path)
        if formatting_errors:
            # Les erreurs de formatage sont moins critiques que les erreurs de validation.
            logger.warning(f"Erreurs de formatage mineures détectées : {formatting_errors}")
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la création du fichier Excel : {e}")
        raise HTTPException(status_code=500, detail="Impossible de générer le fichier Excel en raison d'une erreur interne.")

    # Ajoute une tâche de fond pour supprimer le fichier temporaire après l'envoi de la réponse.
    background_tasks.add_task(os.remove, output_path)

    logger.info(f"Fichier Excel '{output_path}' généré et prêt à être envoyé.")
    return FileResponse(output_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=request.filename)


# --- Pour un lancement direct (débogage/développement) --- #
if __name__ == "__main__":
    import uvicorn
    logger.info("Lancement du service Excel...")
    uvicorn.run(app, host="0.0.0.0", port=8003)