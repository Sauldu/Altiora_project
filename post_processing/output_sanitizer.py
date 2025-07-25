# post_processing/output_sanitizer.py
"""Module pour nettoyer et assainir les sorties brutes des modèles de langage (LLM).

Ce module est essentiel pour normaliser les réponses des LLM avant qu'elles ne soient
utilisées par d'autres parties du système. Il effectue plusieurs opérations clés :
- Supprime les blocs de code Markdown (ex: ```python ... ```).
- Masque les informations personnelles identifiables (PII) en utilisant `PrivacyPolicy`.
- Supprime les instructions de débogage (comme `print()` et `logging.*`).
"""

import re

from policies.privacy_policy import PrivacyPolicy

# ------------------------------------------------------------------
# Constantes et Expressions Régulières
# ------------------------------------------------------------------

# Trouve et extrait le contenu des blocs de code Markdown.
CODE_BLOCK_RE = re.compile(r"^```(?:python)?\s*\n(.*?)\n```\s*$", re.DOTALL)

# Supprime les phrases d'introduction courantes générées par les LLM.
INTRO_RE = re.compile(r"^(?i)(voici|bien sûr, voici) le code.*?\n", re.MULTILINE)

# Supprime les appels à `print()`.
PRINT_RE = re.compile(r"^\s*print\(.*\)\s*$", re.MULTILINE)

# Supprime les appels de logging de bas niveau.
LOG_RE = re.compile(r"^\s*logging\.(?:info|debug|warning)\(.*\)\s*$", re.MULTILINE)


class OutputSanitizer:
    """Nettoyeur rapide et sans configuration pour les sorties de texte et de code."""

    def __init__(self) -> None:
        """Initialise le nettoyeur avec une instance de PrivacyPolicy."""
        self.privacy = PrivacyPolicy()

    def sanitize(
            self,
            text: str,
            *,
            remove_debug: bool = True,
    ) -> str:
        """Nettoie et assainit une chaîne de caractères brute.

        Args:
            text: La chaîne de caractères brute à nettoyer.
            remove_debug: Si True, supprime les instructions de débogage (print, logging).

        Returns:
            La chaîne de caractères nettoyée et avec les PII masquées.
        """
        # 1. Supprime les wrappers Markdown et les introductions.
        text = CODE_BLOCK_RE.sub(r"\1", text.strip())
        text = INTRO_RE.sub("", text)

        # 2. Supprime les instructions de débogage si l'option est activée.
        if remove_debug:
            text = PRINT_RE.sub("", text)
            text = LOG_RE.sub("", text)

        # 3. Masque les PII en utilisant la politique de confidentialité.
        privacy_report = self.privacy.scan_and_mask(text)
        
        # Retourne le texte masqué et nettoyé des espaces superflus.
        return privacy_report.text.strip()


# ------------------------------------------------------------------
# Auto-test rapide
# ------------------------------------------------------------------
if __name__ == "__main__":
    sanitizer = OutputSanitizer()

    raw_text = '''
Bien sûr, voici le code que vous avez demandé :
```python
import os

# Ceci est un commentaire de test
print("Début du script")
logging.info(f"Email de contact : test@example.com")
# Fin du script
```
    '''
    cleaned_text = sanitizer.sanitize(raw_text, remove_debug=True)
    
    print("--- Texte Original ---")
    print(raw_text)
    print("\n--- Texte Nettoyé ---")
    print(cleaned_text)

    # Vérifications pour le test
    assert "```" not in cleaned_text
    assert "Bien sûr" not in cleaned_text
    assert "print(" not in cleaned_text
    assert "logging.info" not in cleaned_text
    assert "test@****.com" in cleaned_text
    assert "# Ceci est un commentaire de test" in cleaned_text
    print("\n✅ Les tests de nettoyage ont réussi.")