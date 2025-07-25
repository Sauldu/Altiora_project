# src/middleware/__init__.py
"""Initialise le package des middlewares de l'application Altiora.

Ce package contient les middlewares FastAPI qui interceptent les requêtes
et les réponses HTTP pour appliquer des logiques transversales telles que
la limitation de débit, la mise en cache et le contrôle d'accès basé sur les rôles (RBAC).

Les modules suivants sont exposés pour faciliter les importations :
- `AdvancedRateLimiter`: Pour la gestion avancée de la limitation de débit.
- `cache_middleware`: Middleware pour la mise en cache des réponses HTTP.
- `rbac_middleware`: Middleware pour la vérification des permissions RBAC.
"""
from .advanced_rate_limiter import AdvancedRateLimiter
from .cache_middleware import cache_middleware
from .rbac_middleware import rbac_middleware

__all__ = ['AdvancedRateLimiter', 'cache_middleware', 'rbac_middleware']
