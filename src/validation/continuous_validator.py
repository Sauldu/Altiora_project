# src/validation/continuous_validator.py
"""Module pour la validation continue des modifications de code.

Ce module implémente un système de validation continue qui permet de
vérifier la qualité, la sécurité, la performance et la conformité des
modifications (commits) avant qu'elles ne soient intégrées. Il agrège
les résultats de plusieurs validateurs spécialisés et peut bloquer les
commits non conformes.
"""

import logging
from typing import Any, Dict

# Supposons que ces classes de validateurs et de rapport sont définies ailleurs
# ou importées. Pour la documentation, nous décrivons leur rôle.
# from .code_quality_validator import CodeQualityValidator
# from .security_validator import SecurityValidator
# from .performance_validator import PerformanceValidator
# from .ai_model_validator import AIModelValidator
# from .validation_report import ValidationReport, ValidationError

logger = logging.getLogger(__name__)


# Classes factices pour la démonstration et la documentation.
class CodeQualityValidator:
    def __init__(self): self.name = "CodeQuality"
    async def validate(self, commit_hash: str) -> Dict[str, Any]:
        # Logique de validation de la qualité du code.
        return {"is_blocking": False, "passed": True, "message": "Qualité du code OK."}

class SecurityValidator:
    def __init__(self): self.name = "Security"
    async def validate(self, commit_hash: str) -> Dict[str, Any]:
        # Logique de validation de la sécurité.
        return {"is_blocking": True, "passed": True, "message": "Sécurité OK."}

class PerformanceValidator:
    def __init__(self): self.name = "Performance"
    async def validate(self, commit_hash: str) -> Dict[str, Any]:
        # Logique de validation de la performance.
        return {"is_blocking": False, "passed": True, "message": "Performance OK."}

class AIModelValidator:
    def __init__(self): self.name = "AIModel"
    async def validate(self, commit_hash: str) -> Dict[str, Any]:
        # Logique de validation des modèles IA.
        return {"is_blocking": False, "passed": True, "message": "Modèle IA OK."}

class ValidationError(Exception):
    """Exception levée lorsqu'une validation bloquante échoue."""
    pass

class ValidationReport:
    """Rapport agrégé des résultats de validation."""
    def __init__(self, results: Dict[str, Any]):
        self.results = results
        self.overall_passed = all(r["passed"] for r in results.values())


class ContinuousValidator:
    """Orchestre l'exécution de divers validateurs pour un commit donné."

    Cette classe est le point d'entrée pour lancer un cycle de validation
    complet. Elle agrège les résultats de chaque validateur et peut déclencher
    une erreur si une validation bloquante échoue.
    """

    def __init__(self):
        """Initialise le validateur continu avec une liste de validateurs spécialisés."""
        self.validators = [
            CodeQualityValidator(),
            SecurityValidator(),
            PerformanceValidator(),
            AIModelValidator()
        ]
        logger.info("ContinuousValidator initialisé avec %d validateurs.", len(self.validators))

    async def validate_commit(self, commit_hash: str) -> ValidationReport:
        """Valide un commit spécifique en exécutant tous les validateurs configurés."

        Args:
            commit_hash: Le hachage (hash) du commit à valider.

        Returns:
            Un objet `ValidationReport` contenant les résultats détaillés de chaque validateur.

        Raises:
            ValidationError: Si l'un des validateurs configurés comme 'bloquant' échoue.
        """
        results: Dict[str, Any] = {}
        logger.info(f"Démarrage de la validation pour le commit : {commit_hash}")

        for validator_instance in self.validators:
            logger.info(f"Exécution du validateur : {validator_instance.name}...")
            try:
                # Exécute la validation pour chaque validateur.
                result = await validator_instance.validate(commit_hash)
                results[validator_instance.name] = result
                logger.info(f"Validateur {validator_instance.name} terminé. Passé : {result["passed"]}")

                # Si le validateur est bloquant et qu'il a échoué, lève une exception.
                if result.get("is_blocking", False) and not result["passed"]:
                    error_message = f"La validation bloquante '{validator_instance.name}' a échoué : {result.get("message", "Aucun message.")}"
                    logger.error(error_message)
                    raise ValidationError(error_message)

            except Exception as e:
                # Capture toute exception inattendue lors de l'exécution d'un validateur.
                error_message = f"Erreur inattendue lors de l'exécution du validateur {validator_instance.name}: {e}"
                logger.critical(error_message, exc_info=True)
                # Enregistre l'échec même si le validateur n'est pas bloquant.
                results[validator_instance.name] = {"is_blocking": True, "passed": False, "message": error_message}
                raise ValidationError(error_message) from e # Re-lève l'exception pour arrêter le processus.

        report = ValidationReport(results)
        if report.overall_passed:
            logger.info(f"Validation du commit {commit_hash} terminée : SUCCÈS.")
        else:
            logger.warning(f"Validation du commit {commit_hash} terminée : ÉCHEC (non bloquant).")
        return report


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def demo():
        validator = ContinuousValidator()

        print("\n--- Démonstration de validation réussie ---")
        try:
            # Simule un commit valide.
            report_success = await validator.validate_commit("abc123def456")
            print(f"Rapport de validation : {report_success.results}")
            print(f"Validation globale réussie : {report_success.overall_passed}")
        except ValidationError as e:
            print(f"Validation échouée (attendu succès) : {e}")

        print("\n--- Démonstration de validation échouée (bloquant) ---")
        # Simule un échec de sécurité (bloquant).
        # Pour cela, nous allons temporairement modifier le validateur de sécurité factice.
        original_security_validate = SecurityValidator.validate
        SecurityValidator.validate = lambda self, commit_hash: {"is_blocking": True, "passed": False, "message": "Vulnérabilité critique détectée !"}

        try:
            report_failure = await validator.validate_commit("ghi789jkl012")
            print(f"Rapport de validation : {report_failure.results}")
            print(f"Validation globale réussie : {report_failure.overall_passed}")
        except ValidationError as e:
            print(f"Validation échouée (attendu échec bloquant) : {e}")
        finally:
            # Restaure le validateur de sécurité.
            SecurityValidator.validate = original_security_validate

        print("Démonstration du ContinuousValidator terminée.")

    asyncio.run(demo())
