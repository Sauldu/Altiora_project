# src/core/__init__.py
"""Initialise le package `core` de l'application Altiora.

Ce package contient les composants fondamentaux et la logique métier
principale de l'application, y compris l'orchestration, la gestion
de la mémoire des modèles, et les systèmes de fallback.

Les modules suivants sont exposés pour faciliter les importations :
- `Container`: Le conteneur de dépendances de l'application.
- `FallbackSystem`: Le système de gestion des stratégies de fallback.
- `ModelMemoryManager`: Le gestionnaire de mémoire pour les modèles d'IA.
"""
from .container import Container
from .fallback_system import FallbackSystem
from .model_memory_manager import ModelMemoryManager

__all__ = ['Container', 'FallbackSystem', 'ModelMemoryManager']
