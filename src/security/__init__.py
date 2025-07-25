# src/security/__init__.py
"""Initialise le package `security` de l'application Altiora.

Ce package contient les modules liés à la sécurité de l'application,
notamment le chiffrement des données, la validation des entrées utilisateur
et la gestion sécurisée des secrets.

Les modules suivants sont exposés pour faciliter les importations :
- `DataEncryption`: Pour les opérations de chiffrement et de déchiffrement.
- `InputValidator`: Pour la validation sécurisée des entrées utilisateur.
- `SecretsManager`: Pour la gestion des secrets de l'application.
"""
from .encryption import DataEncryption
from .input_validator import SFDInput, TestGenerationInput, BatchJobInput, validate_or_422
from .secret_manager import SecretsManager

__all__ = ['DataEncryption', 'SFDInput', 'TestGenerationInput', 'BatchJobInput', 'validate_or_422', 'SecretsManager']
