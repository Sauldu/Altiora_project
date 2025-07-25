"""
Initialise le package `utils` de l'application Altiora.

Ce package contient une collection de fonctions et de classes utilitaires
génériques qui peuvent être utilisées à travers différentes parties de
l'application. Ces utilitaires couvrent des domaines tels que la compression,
la gestion de la mémoire, le chargement de modèles, la gestion des retries,
et d'autres fonctions d'aide.

Les modules et fonctions suivants sont exposés pour faciliter les importations :
- `MemoryOptimizer`: Outil pour l'optimisation de l'utilisation de la mémoire.
- `CompressedCache`: Cache qui utilise la compression pour stocker les données.
- `ModelLoader`: Chargeur et gestionnaire de modèles d'IA.
- `RetryHandler`: Gestionnaire centralisé pour les stratégies de nouvelle tentative.
- `compress_data`: Fonction pour compresser des données.
- `decompress_data`: Fonction pour décompresser des données.
"""
# src/utils/__init__.py
from .memory_optimizer import MemoryOptimizer, CompressedCache
from .model_loader import ModelLoader
from .retry_handler import RetryHandler
from .compression import compress_data, decompress_data

__all__ = ['MemoryOptimizer', 'CompressedCache', 'ModelLoader', 'RetryHandler', 'compress_data', 'decompress_data']