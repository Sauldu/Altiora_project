# src/plugins/__init__.py
"""Initialise le package `plugins` de l'application Altiora.

Ce package contient le système de plugins qui permet d'étendre les
fonctionnalités de l'application de manière dynamique. Il définit
l'interface des plugins et le gestionnaire pour les charger et les exécuter.

Les modules suivants sont exposés pour faciliter les importations :
- `PluginSystem`: Le gestionnaire principal du système de plugins.
"""
from .plugin_system import PluginSystem

__all__ = ['PluginSystem']
