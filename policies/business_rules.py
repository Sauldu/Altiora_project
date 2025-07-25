# policies/business_rules.py
"""
Business-rule validator for generated artefacts (Playwright, Excel, …)
"""

import ast
import re
from typing import List, Dict, Any, Optional

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------
REPORTER_MODULE = "reports.standard_reporter"
REPORTER_FUNC = "report_step"


# ------------------------------------------------------------------
# Rules
# ------------------------------------------------------------------
class BusinessRules:
    """Centralised business-rule checker."""

    async def validate(
            self,
            code_string: str,
            *,
            workflow: str,
            meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return {ok: bool, violations: List[str]}."""
        violations: List[str] = []

        try:
            if workflow == "test":
                violations = self._validate_playwright_test(code_string, meta)
            # Future workflows: elif workflow == "excel": …
        except Exception as e:
            violations.append(f"Unexpected error during validation: {e}")

        return {"ok": not violations, "violations": violations}

    # ----------------------------------------------------------
    # Playwright-specific rules
    # ----------------------------------------------------------
    @staticmethod
    def _validate_playwright_test(
            code: str, meta: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        violations = []

        # 1. No time.sleep()
        if "time.sleep" in code:
            violations.append(
                "Replace time.sleep() with native Playwright waits."
            )

        # 2. No hard-coded URLs
        if re.search(r"page\.goto\(\s*[\"']https?://", code):
            violations.append(
                "Avoid hard-coded URLs; use configuration variables."
            )

        # 3. Import & use reporter utility
        reporter_imported = False
        reporter_used = False
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Import check
                if (
                        isinstance(node, ast.ImportFrom)
                        and node.module == REPORTER_MODULE
                ):
                    reporter_imported = any(
                        alias.name == REPORTER_FUNC for alias in node.names
                    )
                # Usage check
                if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == REPORTER_FUNC
                ):
                    reporter_used = True

                # Docstring & naming
                if isinstance(node, ast.FunctionDef) and node.name.startswith(
                        "test_"
                ):
                    if not ast.get_docstring(node):
                        violations.append(
                            f"Test '{node.name}' lacks a docstring."
                        )
                    if node.name in {"test_unnamed", "test_script"}:
                        violations.append(
                            f"Test name '{node.name}' is too generic."
                        )

        except SyntaxError as e:
            violations.append(f"Python syntax error: {e}")

        if not reporter_imported:
            violations.append(f"Missing import: {REPORTER_MODULE}.{REPORTER_FUNC}")
        if not reporter_used:
            violations.append(f"Missing call to {REPORTER_FUNC}()")

        return violations


# ------------------------------------------------------------------
# Quick demo
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio


    async def main() -> None:
        rules = BusinessRules()

        good = '''
from playwright.sync_api import Page
from reports.standard_reporter import report_step

def test_login(page: Page):
    """Ensure login page loads."""
    report_step("Navigating to login")
    page.goto("/login")
'''

        bad = '''
import time
page.goto("https://example.com")
time.sleep(2)
'''

        logger.info("--- GOOD ---")
        print(await rules.validate(good, workflow="test"))

        logger.info("\n--- BAD ---")
        print(await rules.validate(bad, workflow="test"))


    asyncio.run(main())
