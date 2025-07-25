"""
Initialise le sous-package `qwen3`.

Ce package contient l'interface spécifique pour interagir avec le modèle Qwen3
via Ollama, ainsi que les modules liés à son fine-tuning et à l'adaptation de ses sorties.

Les modules suivants sont exposés pour faciliter les importations :
- `Qwen3OllamaInterface`: L'interface principale pour les interactions avec Qwen3.
"""

# src/models/qwen3/__init__.py
from .qwen3_interface import Qwen3OllamaInterface

__all__ = ['Qwen3OllamaInterface']
