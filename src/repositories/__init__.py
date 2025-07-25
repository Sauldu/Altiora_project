# src/repositories/__init__.py
"""Initialise le package `repositories` de l'application Altiora.

Ce package contient les dépôts (repositories) qui gèrent l'accès aux données
persistantes de l'application. Les dépôts abstraient la logique de stockage
sous-jacente, permettant aux autres parties de l'application d'interagir avec
les données de manière cohérente, quel que soit le type de base de données ou de système de fichiers utilisé.

Les modules suivants sont exposés pour faciliter les importations :
- `BaseRepository`: La classe abstraite de base pour tous les dépôts.
- `ScenarioRepository`: Le dépôt spécifique pour la gestion des scénarios de test.
"""
from .base_repository import BaseRepository
from .scenario_repository import ScenarioRepository

__all__ = ['BaseRepository', 'ScenarioRepository']
