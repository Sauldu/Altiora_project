# src/dashboard/__init__.py
"""Initialise le package du tableau de bord de l'application Altiora.

Ce fichier sert de point d'entrée pour le package `dashboard`,
facilitant l'importation de l'instance de l'application Dash (`app`)
qui définit le tableau de bord de monitoring.
"""
from .app import app

__all__ = ['app']
