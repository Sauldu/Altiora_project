# src/rbac/__init__.py
"""Initialise le package `rbac` (Role-Based Access Control) de l'application Altiora.

Ce package contient les composants nécessaires à la gestion des permissions
et des rôles des utilisateurs, permettant un contrôle d'accès granulaire
aux ressources et fonctionnalités de l'application.

Les modules suivants sont exposés pour faciliter les importations :
- `RBACManager`: Le gestionnaire principal pour les vérifications de permissions.
- `Role`: Modèle de données pour un rôle.
- `Permission`: Modèle de données pour une permission.
- `User`: Modèle de données pour un utilisateur dans le contexte RBAC.
"""
from .manager import RBACManager
from .models import Role, Permission, User

__all__ = ['RBACManager', 'Role', 'Permission', 'User']
