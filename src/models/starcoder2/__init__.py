"""
Initialise le sous-package `starcoder2`.

Ce package contient l'interface spécifique pour interagir avec le modèle StarCoder2
via Ollama, ainsi que les modules liés à la génération de code de test.

Les modules suivants sont exposés pour faciliter les importations :
- `StarCoder2OllamaInterface`: L'interface principale pour les interactions avec StarCoder2.
- `PlaywrightTestConfig`: Modèle de configuration pour les tests Playwright.
- `TestType`: Énumération des types de tests supportés.
"""
# src/models/starcoder2/__init__.py
from .starcoder2_interface import (
    StarCoder2OllamaInterface,
    PlaywrightTestConfig,
    TestType,
)

__all__ = ['StarCoder2OllamaInterface', 'PlaywrightTestConfig', 'TestType']