# src/post_processing/output_sanitizer.py
"""
Clean and sanitise raw LLM outputs.

- Removes markdown code blocks (```python ... ```, ``` ... ```).
- Masks PII using PrivacyPolicy.
- Strips debug statements (print, logging.*).
"""

import re

from policies.privacy_policy import PrivacyPolicy

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------
CODE_BLOCK_RE = re.compile(r"^```(?:python)?\s*\n(.*?)\n```\s*$", re.DOTALL)
INTRO_RE = re.compile(r"^(?i)(voici|bien sûr, voici) le code.*?:\n", re.MULTILINE)
PRINT_RE = re.compile(r"^\s*print\(.*?\)\s*$", re.MULTILINE)
LOG_RE = re.compile(r"^\s*logging\.(?:info|debug|warning)\(.*?\)\s*$", re.MULTILINE)


class OutputSanitizer:
    """Fast, zero-config cleaner for text & code outputs."""

    def __init__(self) -> None:
        self.privacy = PrivacyPolicy()

    def sanitize(
            self,
            text: str,
            *,
            remove_debug: bool = True,
    ) -> str:
        """
        Clean text or code.

        Args:
            text: Raw string.
            remove_debug: Strip print/logging statements.

        Returns:
            Cleaned & PII-masked string.
        """
        # 1. Strip markdown wrappers
        text = CODE_BLOCK_RE.sub(r"\1", text.strip())
        text = INTRO_RE.sub("", text)

        # 2. Remove debug statements (only for code-like blocks)
        if remove_debug:
            text = PRINT_RE.sub("", text)
            text = LOG_RE.sub("", text)

        # 3. Mask PII
        privacy_report = self.privacy.scan_and_mask(text)
        return privacy_report.text.strip()


# ------------------------------------------------------------------
# Quick self-test
# ------------------------------------------------------------------
if __name__ == "__main__":
    sanitizer = OutputSanitizer()

    raw = '''
Bien sûr, voici le code :
```python
import os
logger.info("debug")
logging.info("PII: test@example.com")
    '''
    cleaned = sanitizer.sanitize(raw, remove_debug=True)
    print("--- Original ---\n", raw, "\n--- Clean ---\n", cleaned)
    assert "```" not in cleaned
    assert "debug" not in cleaned
    assert "test@****.com" in cleaned
