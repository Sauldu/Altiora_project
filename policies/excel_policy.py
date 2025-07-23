# src/policies/excel_policy.py
"""
Excel validation rules for test matrices.
Guarantees data integrity before export.
"""

from __future__ import annotations

import re
from typing import List, Dict, Any, Set, Final

# ------------------------------------------------------------------
# Configurable rules
# ------------------------------------------------------------------
TEST_CASE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^CU\d{2}_SB\d{2}_C[PEL]\d{3}_.+(?<!_)$"
)
REQUIRED_COLUMNS: Final[Set[str]] = {"id", "description", "type"}
VALID_TYPES: Final[Set[str]] = {"CP", "CE", "CL"}


class ExcelPolicy:
    """Validates test-case data destined for Excel export."""

    def validate_test_matrix(
        self, test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate a list of test-case dictionaries.

        Returns:
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
    # Rule implementations
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_structure(cases: List[Dict[str, Any]]) -> List[str]:
        """Check required columns."""
        errors = []
        for idx, case in enumerate(cases, start=2):
            missing = REQUIRED_COLUMNS - case.keys()
            if missing:
                errors.append(f"Ligne {idx}: colonnes manquantes {sorted(missing)}")
        return errors

    @staticmethod
    def _validate_content(cases: List[Dict[str, Any]]) -> List[str]:
        """Validate id format, type, and description."""
        errors = []
        for idx, case in enumerate(cases, start=2):
            case_id = str(case.get("id", ""))
            case_type = str(case.get("type", ""))
            description = str(case.get("description", "")).strip()

            if not TEST_CASE_ID_PATTERN.match(case_id):
                errors.append(f"Ligne {idx}: ID '{case_id}' format invalide.")

            if case_type not in VALID_TYPES:
                errors.append(
                    f"Ligne {idx}: type '{case_type}' invalide (attendu {VALID_TYPES})."
                )

            if not description:
                errors.append(f"Ligne {idx}: description vide.")
        return errors

    @staticmethod
    def _validate_uniqueness(cases: List[Dict[str, Any]]) -> List[str]:
        """Ensure unique test-case IDs."""
        seen: Set[str] = set()
        errors = []
        for idx, case in enumerate(cases, start=2):
            case_id = str(case.get("id"))
            if case_id in seen:
                errors.append(f"Ligne {idx}: ID '{case_id}' dupliqué.")
            seen.add(case_id)
        return errors


# ------------------------------------------------------------------
# Quick self-test
# ------------------------------------------------------------------
if __name__ == "__main__":
    policy = ExcelPolicy()

    valid = [
        {
            "id": "CU01_SB01_CP001_connexion_valide",
            "description": "Test connexion réussie.",
            "type": "CP",
        }
    ]
    invalid = [
        {
            "id": "INVALID",
            "description": "",
            "type": "XX",
        }
    ]

    print("Valid data :", policy.validate_test_matrix(valid))
    print("Invalid data:", policy.validate_test_matrix(invalid))