"""
Service web pour la création et la manipulation de fichiers Excel.

Ce service utilise les modules de politique et de formatage pour générer des
fichiers Excel conformes et bien présentés, comme les matrices de test.
"""

import logging
import os
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Importation des modules internes
from policies.excel_policy import ExcelPolicy
from post_processing.excel_formatter import ExcelFormatter

# --- Modèles de Données ---
class TestCase(BaseModel):
    id: str = Field(..., description="L'identifiant unique du cas de test.")
    description: str = Field(..., description="La description du cas de test.")
    type: str = Field(..., description="Le type de cas de test (CP, CE, CL).")

class TestMatrixRequest(BaseModel):
    filename: str = Field(default="matrice_de_test.xlsx", description="Le nom du fichier Excel à générer.")
    test_cases: List[TestCase]


# --- Initialisation de l'application ---
app = FastAPI(
    title="Service de Génération Excel",
    description="Crée des fichiers Excel stylisés à partir de données structurées.",
    version="1.0.0",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_DIR = "temp_excel_reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

policy = ExcelPolicy()
formatter = ExcelFormatter()


# --- Points de Terminaison ---
@app.get("/health", summary="Vérifie l'état de santé du service")
async def health_check() -> Dict[str, str]:
    """Point de terminaison pour la surveillance de base."""
    return {"status": "ok"}


@app.post("/create-test-matrix", summary="Crée un fichier Excel de matrice de tests")
async def create_test_matrix(request: TestMatrixRequest, background_tasks: BackgroundTasks) -> FileResponse:
    """
    Génère un fichier Excel à partir d'une liste de cas de test.
    
    Le fichier est validé, formaté, et ensuite retourné pour téléchargement.
    """
    logger.info(f"Requête reçue pour créer la matrice de tests : {request.filename}")

    # Convertir les modèles Pydantic en dictionnaires simples
    test_cases_data = [case.dict() for case in request.test_cases]

    # 1. Valider les données avec la politique Excel
    validation_result = policy.validate_test_matrix(test_cases_data)
    if not validation_result["is_valid"]:
        logger.error(f"Validation des données échouée : {validation_result['errors']}")
        raise HTTPException(
            status_code=400,
            detail={"message": "Les données des cas de test sont invalides.", "errors": validation_result["errors"]}
        )

    # 2. Formater le fichier Excel
    output_path = os.path.join(OUTPUT_DIR, request.filename)
    try:
        formatting_errors = formatter.format_test_matrix(test_cases_data, output_path)
        if formatting_errors:
            # Ces erreurs sont moins critiques que la validation, on les logue seulement
            logger.warning(f"Erreurs de formatage mineures : {formatting_errors}")
    except Exception as e:
        logger.error(f"Erreur lors de la création du fichier Excel : {e}")
        raise HTTPException(status_code=500, detail="Impossible de générer le fichier Excel.")

    # Ajouter une tâche de fond pour nettoyer le fichier après l'envoi
    background_tasks.add_task(os.remove, output_path)

    logger.info(f"Fichier Excel '{output_path}' généré et prêt à être envoyé.")
    return FileResponse(output_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=request.filename)


# --- Pour un lancement direct (débogage) ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Lancement du service Excel sur http://localhost:8003")
    uvicorn.run(app, host="0.0.0.0", port=8003)
