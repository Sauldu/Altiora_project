# policies/business_rules.py
"""Module de validation des règles métier pour les artefacts générés.

Ce module garantit que les artefacts produits par l'IA (comme les scripts de test
Playwright ou les fichiers Excel) respectent un ensemble de règles métier prédéfinies,
assurant ainsi leur qualité, leur cohérence et leur maintenabilité.
"""

import ast
import re
from typing import List, Dict, Any, Optional

# ------------------------------------------------------------------
# Constantes
# ------------------------------------------------------------------

# Le module de reporting standard que tous les tests doivent utiliser.
REPORTER_MODULE = "reports.standard_reporter"
# La fonction de reporting spécifique à appeler à chaque étape du test.
REPORTER_FUNC = "report_step"


# ------------------------------------------------------------------
# Règles
# ------------------------------------------------------------------
class BusinessRules:
    """Validateur centralisé pour les règles métier."""

    async def validate(
            self,
            code_string: str,
            *,
            workflow: str,
            meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Valide un artefact par rapport à un workflow donné.

        Args:
            code_string: La chaîne de caractères de l'artefact à valider (ex: code Python).
            workflow: Le type de workflow (ex: 'test', 'excel'). Détermine quel
                      ensemble de règles appliquer.
            meta: Métadonnées supplémentaires pouvant être utilisées par les règles.

        Returns:
            Un dictionnaire contenant le résultat de la validation:
            {"ok": bool, "violations": List[str]}
        """
        violations: List[str] = []

        try:
            if workflow == "test":
                violations = self._validate_playwright_test(code_string, meta)
            # D'autres workflows peuvent être ajoutés ici.
            # elif workflow == "excel":
            #     violations = self._validate_excel_file(meta)
        except Exception as e:
            violations.append(f"Erreur inattendue lors de la validation : {e}")

        return {"ok": not violations, "violations": violations}

    # ----------------------------------------------------------
    # Règles spécifiques à Playwright
    # ----------------------------------------------------------
    @staticmethod
    def _validate_playwright_test(
            code: str, meta: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Applique un ensemble de règles spécifiques aux tests Playwright."""
        violations = []

        # Règle 1: Interdire `time.sleep()` au profit des attentes natives de Playwright.
        if "time.sleep" in code:
            violations.append(
                "Règle violée : `time.sleep()` est interdit. Utilisez les attentes natives de Playwright (ex: `page.wait_for_selector`)."
            )

        # Règle 2: Éviter les URLs en dur pour favoriser la configuration.
        if re.search(r"page\.goto\(\s*["']https?://", code):
            violations.append(
                "Règle violée : Les URLs ne doivent pas être codées en dur. Utilisez des variables de configuration."
            )

        # Règle 3: S'assurer de l'utilisation du module de reporting standard.
        reporter_imported = False
        reporter_used = False
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Vérification de l'importation.
                if (
                        isinstance(node, ast.ImportFrom)
                        and node.module == REPORTER_MODULE
                ):
                    reporter_imported = any(
                        alias.name == REPORTER_FUNC for alias in node.names
                    )
                # Vérification de l'utilisation.
                if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == REPORTER_FUNC
                ):
                    reporter_used = True

                # Règle 4: Vérifier la qualité des noms et des docstrings des fonctions de test.
                if isinstance(node, ast.FunctionDef) and node.name.startswith(
                        "test_"
                ):
                    if not ast.get_docstring(node):
                        violations.append(
                            f"Qualité : Le test `{node.name}` n'a pas de docstring."
                        )
                    if node.name in {"test_unnamed", "test_script"}:
                        violations.append(
                            f"Qualité : Le nom du test `{node.name}` est trop générique."
                        )

        except SyntaxError as e:
            violations.append(f"Erreur de syntaxe Python : {e}")

        if not reporter_imported:
            violations.append(f"Règle violée : L'import `{REPORTER_MODULE}.{REPORTER_FUNC}` est manquant.")
        if not reporter_used:
            violations.append(f"Règle violée : La fonction de reporting `{REPORTER_FUNC}()` n'est pas appelée.")

        return violations


# ------------------------------------------------------------------
# Démonstration rapide
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO)

    async def main() -> None:
        rules = BusinessRules()

        good_code = '''
from playwright.sync_api import Page
from reports.standard_reporter import report_step

def test_login_page(page: Page):
    """Vérifie que la page de connexion se charge correctement."""
    report_step("Navigation vers la page de connexion")
    page.goto("/login")
'''

        bad_code = '''
import time

def test_unnamed(page):
    page.goto("https://example.com")
    time.sleep(2)
'''

        logging.info("--- Validation du bon code ---")
        good_result = await rules.validate(good_code, workflow="test")
        logging.info(good_result)

        logging.info("\n--- Validation du mauvais code ---")
        bad_result = await rules.validate(bad_code, workflow="test")
        logging.info(bad_result)

    asyncio.run(main())