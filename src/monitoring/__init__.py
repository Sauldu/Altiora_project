# src/monitoring/__init__.py
"""Initialise le package `monitoring` de l'application Altiora.

Ce package contient les modules liés à la surveillance et à l'observabilité
de l'application, y compris les vérifications de santé, la collecte de métriques
et le traçage distribué.

Les modules suivants sont exposés pour faciliter les importations :
- `healthcheck_app`: L'application FastAPI pour les vérifications de santé.
- `MetricsCollector`: Le collecteur de métriques Prometheus.
"""
from .healthcheck import app as healthcheck_app
from .metrics_collector import MetricsCollector

__all__ = ['healthcheck_app', 'MetricsCollector']
