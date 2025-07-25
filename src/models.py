# src/models.py
"""Modèles de données Pydantic pour les entités de base de l'application Altiora.

Ce module définit les structures de données utilisées pour représenter
les utilisateurs, les rapports et les tests. Ces modèles sont utilisés
pour la validation des données, la sérialisation/désérialisation et
la clarté du code.
"""

from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List


class User(BaseModel):
    """Modèle Pydantic pour représenter un utilisateur."

    Ce modèle est une version simplifiée de l'utilisateur, principalement
    utilisée pour l'authentification et l'autorisation.
    """
    id: str = Field(..., description="Identifiant unique de l'utilisateur.")
    username: str = Field(..., description="Nom d'utilisateur.")
    roles: List[str] = Field(..., description="Liste des rôles de l'utilisateur.")


class Report(BaseModel):
    """Modèle Pydantic pour représenter un rapport généré par l'application."

    Les rapports peuvent inclure des analyses de SFD, des résultats de tests, etc.
    """
    id: str = Field(..., description="Identifiant unique du rapport.")
    title: str = Field(..., description="Titre du rapport.")
    content: str = Field(..., description="Contenu textuel du rapport.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Date et heure de création du rapport (UTC).")


class Test(BaseModel):
    """Modèle Pydantic pour représenter un test exécuté ou généré."

    Ce modèle capture les informations clés d'un test, y compris son statut.
    """
    id: str = Field(..., description="Identifiant unique du test.")
    name: str = Field(..., description="Nom du test.")
    status: str = Field(..., description="Statut actuel du test (ex: 'passed', 'failed', 'running').")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Date et heure de création du test (UTC).")


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("\n--- Démonstration du modèle User ---")
    user_example = User(id="user_1", username="alice", roles=["admin", "editor"])
    print(f"Utilisateur : {user_example.model_dump_json(indent=2)}")

    print("\n--- Démonstration du modèle Report ---")
    report_example = Report(
        id="report_001",
        title="Analyse SFD V1.0",
        content="Contenu détaillé de l'analyse..."
    )
    print(f"Rapport : {report_example.model_dump_json(indent=2)}")

    print("\n--- Démonstration du modèle Test ---")
    test_example = Test(
        id="test_abc",
        name="Test de connexion",
        status="passed"
    )
    print(f"Test : {test_example.model_dump_json(indent=2)}")

    # Exemple de validation (Pydantic lève une erreur si les données sont invalides).
    try:
        invalid_user = User(id="", username="", roles=[])
    except Exception as e:
        print(f"\nErreur de validation attendue pour un utilisateur invalide : {e}")

    print("Démonstration des modèles terminée.")
