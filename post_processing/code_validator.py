"""
Module pour la validation du code Python et Playwright généré.

Ce module fournit une classe `CodeValidator` qui effectue plusieurs vérifications
sur une chaîne de code source pour garantir sa qualité et sa conformité
aux standards du projet.

Fonctionnalités :
1.  Vérification de la syntaxe Python à l'aide du module `ast`.
2.  Linting du code à l'aide de `ruff`.
3.  Vérification du formatage du code avec `black`.
4.  Vérifications spécifiques à Playwright (imports, usage de la fixture `page`, présence d'actions et d'assertions).

Le validateur est conçu pour être utilisé de manière asynchrone et retourne un
objet Pydantic `ValidationResult` détaillé.
"""

import asyncio
import ast
import re
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    """
    Représente le résultat de la validation du code.
    """
    is_valid: bool = Field(True, description="Le code est-il syntaxiquement valide ?")
    syntax_error: Optional[str] = Field(None, description="Message d'erreur de syntaxe, le cas échéant.")
    linting_errors: List[str] = Field(default_factory=list, description="Liste des erreurs de linting (ruff).")
    formatting_errors: List[str] = Field(default_factory=list, description="Liste des erreurs de formatage (black).")
    playwright_warnings: List[str] = Field(default_factory=list, description="Avertissements spécifiques à Playwright.")

    @property
    def passed(self) -> bool:
        """
        Indique si le code a passé toutes les vérifications.
        """
        return self.is_valid and not self.linting_errors and not self.formatting_errors and not self.playwright_warnings


class CodeValidator:
    """
    Valide une chaîne de code Python ou Playwright.
    """

    def __init__(self, ruff_config_path: Optional[str] = None):
        self.ruff_config_path = ruff_config_path

    async def _run_subprocess(self, command: str, *args: str) -> Tuple[int, str, str]:
        process = await asyncio.create_subprocess_exec(
            command, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return process.returncode, stdout.decode('utf-8'), stderr.decode('utf-8')

    def _validate_playwright_specifics(self, code_string: str) -> List[str]:
        """Vérifie les meilleures pratiques spécifiques à Playwright."""
        warnings = []

        # 1. Vérifier l'import de Playwright
        if not re.search(r"from\s+playwright\.(sync|async)_api\s+import", code_string):
            warnings.append("Import Playwright manquant (ex: from playwright.sync_api import Page, expect).")

        # 2. Vérifier l'utilisation de la fixture `page: Page`
        if not re.search(r"def\s+test_\w+\(.*\bpage:\s*Page\b.*\):", code_string):
            warnings.append("La fonction de test doit utiliser la fixture `page: Page` (ex: def test_example(page: Page):).")

        # 3. Vérifier la présence d'au moins une action
        action_pattern = r"\bpage\.(goto|click|fill|press|select_option|check|uncheck|set_input_files|hover|focus|dispatch_event|drag_and_drop|tap|type)\("
        if not re.search(action_pattern, code_string):
            warnings.append("Aucune action Playwright détectée (ex: page.goto(), page.click()).")

        # 4. Vérifier la présence d'au moins une assertion
        if "expect(" not in code_string:
            warnings.append("Aucune assertion Playwright `expect()` détectée. Un test doit valider un résultat.")

        return warnings

    async def validate(self, code_string: str, code_type: str = "python") -> ValidationResult:
        """
        Effectue toutes les validations sur la chaîne de code fournie.
        """
        # 1. Vérification de la syntaxe Python
        try:
            ast.parse(code_string)
        except SyntaxError as e:
            return ValidationResult(
                is_valid=False,
                syntax_error=f"Erreur de syntaxe à la ligne {e.lineno}, offset {e.offset}: {e.msg}"
            )

        result = ValidationResult()

        # 2. Vérifications spécifiques à Playwright
        if code_type == "playwright":
            result.playwright_warnings = self._validate_playwright_specifics(code_string)

        # Utilise un fichier temporaire pour les outils CLI
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.py', delete=False, encoding='utf-8') as temp_file:
            temp_file_path = Path(temp_file.name)
            temp_file.write(code_string)
            temp_file.flush()

        try:
            # 3. Linting avec Ruff
            ruff_args = ['check', str(temp_file_path), '--quiet']
            if self.ruff_config_path:
                ruff_args.extend(['--config', self.ruff_config_path])
            
            ruff_code, ruff_stdout, _ = await self._run_subprocess('ruff', *ruff_args)
            if ruff_code != 0:
                result.linting_errors = [line for line in ruff_stdout.strip().split('\n') if line]

            # 4. Vérification du formatage avec Black
            black_code, _, black_stderr = await self._run_subprocess('black', '--check', '--quiet', str(temp_file_path))
            if black_code != 0:
                result.formatting_errors = [line for line in black_stderr.strip().split('\n') if line]

        finally:
            temp_file_path.unlink()

        return result


async def main():
    """
    Fonction principale pour une démonstration et un test rapide du validateur.
    """
    validator = CodeValidator()

    # --- Cas de tests Python ---
    good_code = "import os\n\ndef get_cwd():\n    return os.getcwd()\n\nprint(get_cwd())\n"
    bad_syntax_code = "import os\nprint(os.getcwd("
    bad_style_code = "import os,sys\ndef myFunction( x,y): return x>y"

    print("--- Test Python valide ---")
    result_good = await validator.validate(good_code)
    print(f"Passé: {result_good.passed}\n{result_good.dict(exclude_defaults=True)}\n")
    assert result_good.passed

    print("--- Test Python syntaxe incorrecte ---")
    result_syntax = await validator.validate(bad_syntax_code)
    print(f"Passé: {result_syntax.passed}\n{result_syntax.dict(exclude_defaults=True)}\n")
    assert not result_syntax.passed and result_syntax.syntax_error

    print("--- Test Python style incorrect ---")
    result_style = await validator.validate(bad_style_code)
    print(f"Passé: {result_style.passed}\n{result_style.dict(exclude_defaults=True)}\n")
    assert not result_style.passed and (result_style.linting_errors or result_style.formatting_errors)

    # --- Cas de tests Playwright ---
    valid_playwright_code = '''
from playwright.sync_api import Page, expect

def test_homepage_has_title(page: Page):
    page.goto("https://playwright.dev/")
    expect(page).to_have_title(re.compile("Playwright"))
'''
    invalid_playwright_code = '''
# Manque l'import, l'action et l'assertion
def test_does_nothing(page):
    pass
'''
    print("--- Test Playwright valide ---")
    result_pw_good = await validator.validate(valid_playwright_code, code_type="playwright")
    print(f"Passé: {result_pw_good.passed}\n{result_pw_good.dict(exclude_defaults=True)}\n")
    assert result_pw_good.passed

    print("--- Test Playwright invalide (manque de bonnes pratiques) ---")
    result_pw_bad = await validator.validate(invalid_playwright_code, code_type="playwright")
    print(f"Passé: {result_pw_bad.passed}\n{result_pw_bad.dict(exclude_defaults=True)}\n")
    assert not result_pw_bad.passed and result_pw_bad.playwright_warnings


if __name__ == "__main__":
    print("Exécution des tests du CodeValidator...")
    asyncio.run(main())
    print("\nTests terminés.")
