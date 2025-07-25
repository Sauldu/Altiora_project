# docs/generate_docs.py
from pathlib import Path
import json

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


class DocumentationGenerator:
    def __init__(self, source_dir: Path):
        self.source_dir = source_dir
        self.docs = {}

    def generate(self):
        """Génère la documentation complète du projet"""
        # 1. API Documentation
        self._generate_api_docs()

        # 2. Architecture diagrams
        self._generate_architecture_diagrams()

        # 3. Deployment guide
        self._generate_deployment_guide()

        # 4. Performance benchmarks
        self._generate_performance_docs()

    def _generate_api_docs(self):
        """Génère la documentation OpenAPI/Swagger"""
        # Import dynamique de l'app
        import sys
        sys.path.append(str(self.source_dir))
        from main import app

        openapi_schema = get_openapi(
            title="Altiora QA Automation API",
            version="1.0.0",
            description="API pour l'automatisation des tests avec IA",
            routes=app.routes,
        )

        try:
            with open("docs/openapi.json", "w") as f:
                json.dump(openapi_schema, f, indent=2)
        except (IOError, OSError) as e:
            logger.info(f"Error writing OpenAPI spec: {e}")