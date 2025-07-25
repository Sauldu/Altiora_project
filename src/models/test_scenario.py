from typing import Dict, Any, List

from pydantic import BaseModel, Field


class TestScenario(BaseModel):
    """Modèle Pydantic pour représenter un scénario de test détaillé.

    Ce modèle est utilisé pour structurer les informations d'un scénario de test,
    qu'il soit extrait d'une SFD ou créé manuellement.
    """
    id: str = Field(..., description="Identifiant unique du scénario de test.")
    title: str = Field(..., min_length=5, description="Titre descriptif du scénario de test.")
    objective: str = Field(..., description="Objectif principal du scénario de test.")
    criticality: str = Field("MEDIUM", description="Niveau de criticité du test (HIGH, MEDIUM, LOW).")
    preconditions: List[str] = Field(default_factory=list, description="Liste des préconditions nécessaires à l'exécution du test.")
    steps: List[str] = Field(..., min_items=1, description="Étapes détaillées à suivre pour exécuter le test.")
    expected_result: str = Field(..., description="Résultat attendu après l'exécution du test.")
    test_data: Dict[str, Any] = Field(default_factory=dict, description="Données spécifiques requises pour l'exécution du test.")
    test_type: str = Field("FUNCTIONAL", description="Type de test (FUNCTIONAL, INTEGRATION, E2E, SECURITY, PERFORMANCE).")

    class Config:
        # Permet d'utiliser les valeurs des Enums directement dans les champs du modèle.
        use_enum_values = True


class TestSuite(BaseModel):
    """Modèle Pydantic pour représenter une suite de tests, composée de plusieurs scénarios."""
    name: str = Field(..., description="Nom de la suite de tests.")
    description: str = Field(..., description="Description de la suite de tests.")
    scenarios: List[TestScenario] = Field(default_factory=list, description="Liste des scénarios de test inclus dans cette suite.")