# src/api/openapi.py
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def custom_openapi(app: FastAPI):
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Altiora API",
        version="1.0.0",
        description="API pour l'assistant QA Altiora",
        routes=app.routes,
    )

    # Ajouter des exemples personnalisés
    openapi_schema["paths"]["/analyze-sfd"]["post"]["requestBody"]["content"]["application/json"]["example"] = {
        "content": "Spécification fonctionnelle...",
        "project_id": "proj-123"
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema