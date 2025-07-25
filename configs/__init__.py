# configs/__init__.py
"""Initialise le package de configuration de l'application Altiora.

Ce fichier sert de point d'entrée pour le package `configs`,
facilitant l'importation des classes de configuration et de la fonction
`get_settings` qui charge l'instance singleton de la configuration globale.
"""
from .settings_loader import UnifiedSettings, get_settings

__all__ = ['UnifiedSettings', 'get_settings']
