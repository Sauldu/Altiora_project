"""
Initialise le package `models` de l'application Altiora.

Ce package regroupe les interfaces avec les différents modèles de langage (LLMs)
utilisés par l'application, ainsi que les modèles de données Pydantic
qui définissent les structures d'information clés (ex: requêtes SFD, scénarios de test).

Les modules suivants sont exposés pour faciliter les importations :
- `Qwen3OllamaInterface`: Interface pour le modèle Qwen3.
- `StarCoder2OllamaInterface`: Interface pour le modèle StarCoder2.
- `SFDAnalysisRequest`: Modèle de données pour les requêtes d'analyse SFD.
- `TestScenario`: Modèle de données pour les scénarios de test.
"""

# src/models/__init__.py
from .qwen3.qwen3_interface import Qwen3OllamaInterface
from .starcoder2.starcoder2_interface import StarCoder2OllamaInterface
from .sfd_models import SFDAnalysisRequest
from .test_scenario import TestScenario

__all__ = ['Qwen3OllamaInterface', 'StarCoder2OllamaInterface', 'SFDAnalysisRequest', 'TestScenario']
