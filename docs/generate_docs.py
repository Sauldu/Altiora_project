# docs/generate_docs.py
"""Module pour la génération automatisée de la documentation du projet Altiora.

Ce script centralise la création de divers artefacts de documentation,
notamment la spécification OpenAPI (Swagger/Redoc) de l'API, des diagrammes
d'architecture, des guides de déploiement et des rapports de performance.
Il vise à maintenir la documentation à jour et cohérente avec le code.
"""

from pathlib import Path
import json
import logging

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

logger = logging.getLogger(__name__)


class DocumentationGenerator:
    """Générateur de documentation pour le projet Altiora."""

    def __init__(self, source_dir: Path):
        """Initialise le générateur de documentation."

        Args:
            source_dir: Le répertoire source de l'application (ex: `src/`).
        """
        self.source_dir = source_dir
        self.docs: Dict[str, Any] = {} # Dictionnaire pour stocker les documents générés.

    def generate(self):
        """Génère la documentation complète du projet en appelant les méthodes spécifiques."

        Cette méthode orchestre le processus de génération de documentation.
        """
        logger.info("Démarrage de la génération de la documentation...")
        # 1. Documentation de l'API (OpenAPI/Swagger).
        self._generate_api_docs()

        # 2. Diagrammes d'architecture (placeholder).
        self._generate_architecture_diagrams()

        # 3. Guide de déploiement (placeholder).
        self._generate_deployment_guide()

        # 4. Rapports de performance (placeholder).
        self._generate_performance_docs()
        logger.info("Génération de la documentation terminée.")

    def _generate_api_docs(self):
        """Génère la spécification OpenAPI (Swagger/Redoc) de l'API FastAPI."

        Cette méthode importe dynamiquement l'application FastAPI et utilise
        `get_openapi` pour créer le schéma, puis le sauvegarde au format JSON.
        """
        logger.info("Génération de la documentation API (OpenAPI/Swagger)...")
        # Ajoute le répertoire source au chemin système pour permettre l'importation de l'application FastAPI.
        import sys
        sys.path.append(str(self.source_dir))
        
        try:
            # Importe l'instance de l'application FastAPI.
            from main import app

            # Génère le schéma OpenAPI.
            openapi_schema = get_openapi(
                title="Altiora QA Automation API",
                version="1.0.0",
                description="API pour l'automatisation des tests avec IA, l'analyse de SFD et la gestion des rapports.",
                routes=app.routes,
            )

            # Sauvegarde le schéma OpenAPI dans un fichier JSON.
            output_path = Path("docs/openapi.json")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(openapi_schema, f, indent=2, ensure_ascii=False)
            logger.info(f"Spécification OpenAPI générée et sauvegardée : {output_path}")
        except ImportError:
            logger.error(f"Impossible d'importer l'application FastAPI depuis {self.source_dir}. Assurez-vous que `main.py` existe et est valide.")
        except (IOError, OSError) as e:
            logger.error(f"Erreur lors de l'écriture de la spécification OpenAPI : {e}")
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la génération de la documentation API : {e}", exc_info=True)

    def _generate_architecture_diagrams(self):
        """Génère les diagrammes d'architecture du projet (placeholder)."

        Cette méthode serait utilisée pour intégrer des outils de génération de diagrammes
        (ex: PlantUML, Mermaid, Graphviz) à partir de définitions textuelles ou de code.
        """
        logger.info("Génération des diagrammes d'architecture (non implémenté)...")
        # TODO: Implémenter la logique de génération de diagrammes.
        pass

    def _generate_deployment_guide(self):
        """Génère le guide de déploiement (placeholder)."

        Cette méthode pourrait assembler des informations provenant de différentes
        sources (fichiers de configuration, scripts Docker) pour créer un guide
        de déploiement complet.
        """
        logger.info("Génération du guide de déploiement (non implémenté)...")
        # TODO: Implémenter la logique de génération du guide de déploiement.
        pass

    def _generate_performance_docs(self):
        """Génère la documentation des benchmarks de performance (placeholder)."

        Cette méthode pourrait analyser les rapports de `pytest-benchmark`
        et générer des visualisations ou des résumés pour la documentation.
        """
        logger.info("Génération de la documentation des performances (non implémenté)...")
        # TODO: Implémenter la logique de génération des docs de performance.
        pass


# ------------------------------------------------------------------
# Point d'entrée CLI
# ------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description="Génère la documentation du projet Altiora.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("src"),
        help="Répertoire source de l'application (contenant main.py)."
    )
    args = parser.parse_args()

    print("\n--- Lancement de la génération de documentation ---")
    generator = DocumentationGenerator(args.source_dir)
    generator.generate()
    print("Démonstration de la génération de documentation terminée.")
