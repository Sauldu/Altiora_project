# policies/excel_policy.py
"""Module contenant les règles de validation pour les matrices de test.

Ce module garantit l'intégrité des données destinées à être exportées
vers des fichiers Excel, en s'assurant que les cas de test respectent
le format, la structure et le contenu attendus.
"""

from __future__ import annotations

import re
from typing import List, Dict, Any, Set, Final

# ------------------------------------------------------------------
# Règles de configuration
# ------------------------------------------------------------------

# Expression régulière pour valider le format des identifiants de cas de test.
# Exemple de format valide : CU01_SB02_CP001_nom_du_test
TEST_CASE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^CU\d{2}_SB\d{2}_C[PEL]\d{3}_.+(?<!_)$"
)

# Ensemble des colonnes requises dans chaque dictionnaire de cas de test.
REQUIRED_COLUMNS: Final[Set[str]] = {"id", "description", "type"}

# Ensemble des types de cas de test valides.
VALID_TYPES: Final[Set[str]] = {"CP", "CE", "CL"}  # Cas Passant, Cas d'Erreur, Cas Limite


class ExcelPolicy:
    """Valide les données des cas de test avant leur exportation vers Excel."""

    def validate_test_matrix(
        self, test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Valide une liste de dictionnaires représentant des cas de test.

        Args:
            test_cases: Une liste de cas de test, où chaque cas est un dictionnaire.

        Returns:
            Un dictionnaire contenant le statut de la validation et la liste des erreurs.
            {
                "is_valid": bool,
                "errors": List[str]
            }
        """
        errors: List[str] = []
        errors.extend(self._validate_structure(test_cases))
        errors.extend(self._validate_content(test_cases))
        errors.extend(self._validate_uniqueness(test_cases))
        return {"is_valid": not errors, "errors": errors}

    # ------------------------------------------------------------------
    # Implémentation des règles
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_structure(cases: List[Dict[str, Any]]) -> List[str]:
        """Vérifie la présence des colonnes requises dans chaque cas de test."""
        errors = []
        for idx, case in enumerate(cases, start=2):  # Commence à 2 pour correspondre aux lignes Excel
            missing = REQUIRED_COLUMNS - case.keys()
            if missing:
                errors.append(f"Ligne {idx}: Colonnes manquantes {sorted(missing)}.")
        return errors

    @staticmethod
    def _validate_content(cases: List[Dict[str, Any]]) -> List[str]:
        """Valide le format de l'ID, le type et la description de chaque cas."""
        errors = []
        for idx, case in enumerate(cases, start=2):
            case_id = str(case.get("id", ""))
            case_type = str(case.get("type", ""))
            description = str(case.get("description", "")).strip()

            if not TEST_CASE_ID_PATTERN.match(case_id):
                errors.append(f"Ligne {idx}: L'ID `{case_id}` a un format invalide.")

            if case_type not in VALID_TYPES:
                errors.append(
                    f"Ligne {idx}: Le type `{case_type}` est invalide (attendu : {VALID_TYPES})."
                )

            if not description:
                errors.append(f"Ligne {idx}: La description ne peut pas être vide.")
        return errors

    @staticmethod
    def _validate_uniqueness(cases: List[Dict[str, Any]]) -> List[str]:
        """S'assure que chaque identifiant de cas de test est unique."""
        seen: Set[str] = set()
        errors = []
        for idx, case in enumerate(cases, start=2):
            case_id = str(case.get("id"))
            if case_id in seen:
                errors.append(f"Ligne {idx}: L'ID `{case_id}` est dupliqué.")
            seen.add(case_id)
        return errors


# ------------------------------------------------------------------
# Auto-test rapide
# ------------------------------------------------------------------
if __name__ == "__main__":
    policy = ExcelPolicy()

    valid_cases = [
        {
            "id": "CU01_SB01_CP001_connexion_valide",
            "description": "Tester la connexion réussie avec un utilisateur valide.",
            "type": "CP",
        }
    ]
    invalid_cases = [
        {
            "id": "INVALID_ID",
            "description": "",
            "type": "XX",
        },
        {
            "id": "CU01_SB01_CP001_connexion_valide", # ID dupliqué
            "description": "Un autre test.",
            "type": "CP",
        }
    ]

    print("Validation de données valides :", policy.validate_test_matrix(valid_cases))
    print("Validation de données invalides :", policy.validate_test_matrix(invalid_cases))
