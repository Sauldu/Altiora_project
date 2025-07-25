# src/api/openapi.py
"""Module pour la personnalisation de la spécification OpenAPI (Swagger/Redoc) de l'API Altiora.

Ce module permet de définir des métadonnées supplémentaires pour la documentation
de l'API, telles que le titre, la version, la description, et d'ajouter des
exemples de requêtes/réponses pour améliorer la clarté de la documentation
générée automatiquement par FastAPI.
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def custom_openapi(app: FastAPI):
    """Génère et personnalise la spécification OpenAPI pour l'application FastAPI."

    Cette fonction est appelée par FastAPI pour construire la documentation
    interactive (Swagger UI, ReDoc). Elle ajoute des informations spécifiques
    au projet et des exemples pour les endpoints.

    Args:
        app: L'instance de l'application FastAPI.

    Returns:
        Le schéma OpenAPI personnalisé.
    """
    # Si le schéma a déjà été généré, le retourne directement pour éviter de le recréer.
    if app.openapi_schema:
        return app.openapi_schema

    # Génère le schéma OpenAPI de base à partir des routes de l'application.
    openapi_schema = get_openapi(
        title="Altiora API",
        version="1.0.0",
        description="API pour l'assistant QA Altiora, permettant l'automatisation des tests et l'analyse de spécifications.",
        routes=app.routes,
    )

    # Ajoute des exemples personnalisés pour des endpoints spécifiques.
    # Ceci améliore la lisibilité de la documentation Swagger/Redoc.
    if "/analyze-sfd" in openapi_schema["paths"] and "post" in openapi_schema["paths"]["/analyze-sfd"]:
        openapi_schema["paths"]["/analyze-sfd"]["post"]["requestBody"]["content"]["application/json"]["example"] = {
            "content": "Spécification fonctionnelle détaillée du module de connexion utilisateur...",
            "project_id": "proj-123"
        }

    # Stocke le schéma généré dans l'application pour les appels futurs.
    app.openapi_schema = openapi_schema
    return app.openapi_schema
