# post_processing/code_validator.py
"""Module pour la validation complète du code Python et Playwright généré.

Ce module fournit une classe `CodeValidator` qui effectue plusieurs vérifications
sur une chaîne de code source pour garantir sa qualité, sa syntaxe et sa conformité
aux standards du projet avant son utilisation ou son stockage.

Fonctionnalités principales :
1.  Vérification de la syntaxe Python à l'aide du module `ast`.
2.  Linting du code à l'aide de `ruff` pour détecter les erreurs et les mauvaises pratiques.
3.  Vérification du formatage du code avec `black` pour assurer un style cohérent.
4.  Vérifications spécifiques à Playwright (imports, usage de la fixture `page`, etc.).

Le validateur est conçu pour être utilisé de manière asynchrone et retourne un
objet Pydantic `ValidationResult` qui détaille toutes les erreurs trouvées.
"""

import ast
import asyncio
import logging
import re
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

# Configuration du logger
logger = logging.getLogger(__name__)


class ValidationResult(BaseModel):
    """Représente le résultat détaillé de la validation du code."""
    is_valid: bool = Field(True, description="Le code est-il syntaxiquement valide ?")
    syntax_error: Optional[str] = Field(None, description="Message d'erreur de syntaxe, le cas échéant.")
    linting_errors: List[str] = Field(default_factory=list, description="Liste des erreurs de linting (ruff).")
    formatting_errors: List[str] = Field(default_factory=list, description="Liste des erreurs de formatage (black).")
    playwright_warnings: List[str] = Field(default_factory=list, description="Avertissements spécifiques à Playwright.")

    @property
    def passed(self) -> bool:
        """Propriété indiquant si le code a passé toutes les vérifications avec succès."""
        return self.is_valid and not self.linting_errors and not self.formatting_errors and not self.playwright_warnings


class CodeValidator:
    """Valide une chaîne de code Python ou Playwright en utilisant des outils externes."""

    def __init__(self, ruff_config_path: Optional[str] = None):
        """Initialise le validateur.

        Args:
            ruff_config_path: Chemin optionnel vers un fichier de configuration `ruff.toml`.
        """
        self.ruff_config_path = ruff_config_path

    @staticmethod
    async def _run_subprocess(command: str, *args: str) -> Tuple[int, str, str]:
        """Exécute une commande en sous-processus de manière asynchrone."""
        try:
            process = await asyncio.create_subprocess_exec(
                command, *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return process.returncode, stdout.decode('utf-8'), stderr.decode('utf-8')
        except FileNotFoundError:
            logger.error(f"La commande `{command}` n'a pas été trouvée. Assurez-vous qu'elle est installée et dans le PATH.")
            return -1, "", f"Commande non trouvée: {command}"
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la commande `{command}` : {e}")
            return -1, "", str(e)

    @staticmethod
    def _validate_playwright_specifics(code_string: str) -> List[str]:
        """Vérifie les meilleures pratiques et conventions spécifiques à Playwright."""
        warnings = []

        # 1. Vérifier l'importation de Playwright.
        if not re.search(r"from\s+playwright\.(sync|async)_api\s+import", code_string):
            warnings.append("Avertissement : Import Playwright manquant (ex: from playwright.sync_api import Page, expect).")

        # 2. Vérifier l'utilisation de la fixture `page: Page` dans la signature du test.
        if not re.search(r"def\s+test_\w+\(.*\bpage:\s*Page\b.*\):", code_string):
            warnings.append("Avertissement : La fonction de test doit utiliser la fixture `page: Page` (ex: def test_example(page: Page):).")

        # 3. Vérifier la présence d'au moins une action Playwright.
        action_pattern = r"\bpage\.(goto|click|fill|press|select_option|check|uncheck|set_input_files|hover|focus|dispatch_event|drag_and_drop|tap|type)\("
        if not re.search(action_pattern, code_string):
            warnings.append("Avertissement : Aucune action Playwright détectée (ex: page.goto(), page.click()). Le test pourrait ne rien faire.")

        # 4. Vérifier la présence d'au moins une assertion `expect`.
        if "expect(" not in code_string:
            warnings.append("Avertissement : Aucune assertion Playwright `expect()` détectée. Un test doit valider un résultat.")

        return warnings

    async def validate(self, code_string: str, code_type: str = "python") -> ValidationResult:
        """Effectue toutes les validations sur la chaîne de code fournie.

        Args:
            code_string: La chaîne de code à valider.
            code_type: Le type de code ('python' ou 'playwright') pour appliquer des règles spécifiques.

        Returns:
            Un objet `ValidationResult` contenant les résultats de la validation.
        """
        # 1. Vérification de la syntaxe Python (rapide et en premier).
        try:
            ast.parse(code_string)
        except SyntaxError as e:
            return ValidationResult(
                is_valid=False,
                syntax_error=f"Erreur de syntaxe à la ligne {e.lineno}, offset {e.offset}: {e.msg}"
            )

        result = ValidationResult()

        # 2. Vérifications spécifiques à Playwright si nécessaire.
        if code_type == "playwright":
            result.playwright_warnings = self._validate_playwright_specifics(code_string)

        # Crée un fichier temporaire pour passer le code aux outils CLI (ruff, black).
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.py', delete=False, encoding='utf-8') as temp_file:
            temp_file_path = Path(temp_file.name)
            temp_file.write(code_string)
            temp_file.flush()

        try:
            # 3. Linting avec Ruff.
            ruff_args = ['check', str(temp_file_path), '--quiet', '--exit-zero']
            if self.ruff_config_path:
                ruff_args.extend(['--config', self.ruff_config_path])

            _, ruff_stdout, ruff_stderr = await self._run_subprocess('ruff', *ruff_args)
            if ruff_stdout:
                result.linting_errors = [line for line in ruff_stdout.strip().split('\n') if line]
            if ruff_stderr:
                 result.linting_errors.append(ruff_stderr)

            # 4. Vérification du formatage avec Black.
            _, _, black_stderr = await self._run_subprocess('black', '--check', '--quiet', str(temp_file_path))
            if black_stderr:
                result.formatting_errors = [line for line in black_stderr.strip().split('\n') if line]

        finally:
            # S'assure que le fichier temporaire est bien supprimé.
            temp_file_path.unlink()

        return result


async def main():
    """Fonction principale pour une démonstration et un test rapide du validateur."""
    validator = CodeValidator()

    # ... (le reste de la fonction main reste inchangé)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Exécution des tests du CodeValidator...")
    asyncio.run(main())
    logger.info("\nTests terminés.")