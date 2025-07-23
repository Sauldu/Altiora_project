"""
Package Modèles IA – Regroupe Qwen3 & StarCoder2
"""

from .qwen3.qwen3_interface import Qwen3OllamaInterface
from .starcoder2.starcoder2_interface import StarCoder2OllamaInterface

__all__ = ["Qwen3OllamaInterface", "StarCoder2OllamaInterface"]