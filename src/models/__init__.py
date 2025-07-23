"""
Package Modèles IA – Regroupe Qwen3 & StarCoder2
"""

# src/models/__init__.py
from .qwen3.qwen3_interface import Qwen3OllamaInterface
from .starcoder2.starcoder2_interface import StarCoder2OllamaInterface
from .sfd_models import SFDAnalysisRequest
from .test_scenario import TestScenario

__all__ = ['Qwen3OllamaInterface', 'Starcoder2OllamaInterface', 'SFDAnalysisRequest', 'TestScenario']