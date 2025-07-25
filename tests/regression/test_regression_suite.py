# tests/regression/test_regression_suite.py
"""Suite de tests de régression automatiques pour Altiora.

Ce module implémente une suite de tests de régression qui compare les
résultats actuels de l'application avec des références (baselines) stockées.
Il permet de détecter les régressions fonctionnelles ou de performance
introduites par de nouvelles modifications de code. La suite peut être
configurée pour mettre à jour les baselines et générer des rapports détaillés.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import pytest
import yaml

from src.orchestrator import Orchestrator
from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from src.models.starcoder2.starcoder2_interface import StarCoder2OllamaInterface, TestType

logger = logging.getLogger(__name__)


class RegressionTestResult:
    """Représente le résultat d'un test de régression individuel."""

    def __init__(self, test_name: str, status: str, metrics: Dict[str, Any],
                 diff: Optional[str] = None):
        """Initialise un résultat de test de régression."

        Args:
            test_name: Le nom du test de régression.
            status: Le statut du test ('PASS', 'FAIL', 'NEW').
            metrics: Un dictionnaire de métriques associées au test.
            diff: Un string représentant le 'diff' si le test a échoué (optionnel).
        """
        self.test_name = test_name
        self.status = status  # PASS, FAIL, NEW
        self.metrics = metrics
        self.diff = diff
        self.timestamp = datetime.now().isoformat()


class RegressionSuite:
    """Gère l'exécution et l'analyse des tests de régression."""

    def __init__(self, config_path: str = "tests/regression/regression_config.yaml"):
        """Initialise la suite de tests de régression."

        Args:
            config_path: Le chemin vers le fichier de configuration des tests de régression.
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.baseline_path = Path("tests/regression/baselines")
        self.baseline_path.mkdir(parents=True, exist_ok=True)
        self.results_path = Path("tests/regression/results")
        self.results_path.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict[str, Any]:
        """Charge la configuration des tests de régression depuis le fichier YAML."

        Si le fichier n'existe pas, une configuration par défaut est créée.

        Returns:
            Un dictionnaire contenant la configuration des tests de régression.
        """
        if not self.config_path.exists():
            logger.info(f"Fichier de configuration de régression non trouvé à {self.config_path}. Création d'une configuration par défaut.")
            default_config = {
                "thresholds": {
                    "max_time_increase": 1.2,  # Augmentation de temps max de 20%.
                    "min_scenarios": 1,
                    "min_tests_generated": 1,
                    "code_similarity": 0.8 # Seuil de similarité pour le code généré.
                },
                "models": {
                    "qwen3": {
                        "model_name": "qwen3-sfd-analyzer",
                        "test_cases": ["scenario_extraction", "test_matrix"]
                    },
                    "starcoder2": {
                        "model_name": "starcoder2-playwright",
                        "test_cases": ["code_generation", "syntax_validity"]
                    }
                },
                "services": {
                    "health_check": True,
                    "response_time": 30  # secondes max.
                },
                "update_baselines": False, # Option pour mettre à jour les baselines.
                "generate_report": True # Option pour générer un rapport HTML.
            }
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, indent=2)
        return yaml.safe_load(self.config_path.read_text(encoding='utf-8'))

    async def run_full_regression(self) -> Dict[str, Any]:
        """Exécute la suite complète de tests de régression."

        Returns:
            Un dictionnaire contenant les résultats détaillés de tous les tests de régression,
            un résumé et des métriques de performance.
        """
        logger.info("🔄 Début des tests de régression...")

        results = {
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "summary": {"passed": 0, "failed": 0, "new": 0},
            "performance_metrics": {}
        }

        # Exécution des tests de régression pour les modèles LLM.
        model_results = await self._test_models_regression()
        results["tests"].extend(model_results)

        # Exécution des tests de régression pour le pipeline complet.
        pipeline_results = await self._test_pipeline_regression()
        results["tests"].extend(pipeline_results)

        # Exécution des tests de régression de performance.
        perf_results = await self._test_performance_regression()
        results["performance_metrics"] = perf_results

        # Mise à jour du résumé des résultats.
        results["summary"] = {
            "passed": sum(1 for t in results["tests"] if t.status == "PASS"),
            "failed": sum(1 for t in results["tests"] if t.status == "FAIL"),
            "new": sum(1 for t in results["tests"] if t.status == "NEW")
        }

        # Génération du rapport HTML si configuré.
        if self.config.get("generate_report", True):
            self._generate_regression_report(results)

        # Mise à jour des baselines si configuré.
        if self.config.get("update_baselines", False):
            await self._update_baselines(results)

        logger.info("✅ Tests de régression terminés.")
        return results

    async def _test_models_regression(self) -> List[RegressionTestResult]:
        """Exécute les tests de régression spécifiques aux modèles LLM (Qwen3, StarCoder2)."

        Returns:
            Une liste de `RegressionTestResult` pour les tests des modèles.
        """
        results = []

        logger.info("Exécution des tests de régression Qwen3...")
        qwen3_results = await self._test_qwen3_regression()
        results.extend(qwen3_results)

        logger.info("Exécution des tests de régression StarCoder2...")
        starcoder_results = await self._test_starcoder2_regression()
        results.extend(starcoder_results)

        return results

    async def _test_qwen3_regression(self) -> List[RegressionTestResult]:
        """Exécute les tests de régression pour le modèle Qwen3."

        Returns:
            Une liste de `RegressionTestResult` pour les tests Qwen3.
        """
        results = []
        qwen3 = Qwen3OllamaInterface() # Assurez-vous que cette instance est correctement configurée.
        await qwen3.initialize()

        try:
            test_cases = self._load_test_cases("qwen3")

            for test_case in test_cases:
                test_name = f"qwen3_{test_case['name']}"
                # Exécute le test Qwen3 et compare avec la baseline.
                result = await self._run_single_qwen3_test(qwen3, test_case, test_name)
                results.append(result)

        finally:
            await qwen3.close()

        return results

    async def _test_starcoder2_regression(self) -> List[RegressionTestResult]:
        """Exécute les tests de régression pour le modèle StarCoder2."

        Returns:
            Une liste de `RegressionTestResult` pour les tests StarCoder2.
        """
        results = []
        starcoder = StarCoder2OllamaInterface() # Assurez-vous que cette instance est correctement configurée.
        await starcoder.initialize()

        try:
            test_cases = self._load_test_cases("starcoder2")

            for test_case in test_cases:
                test_name = f"starcoder2_{test_case['name']}"
                # Exécute le test StarCoder2 et compare avec la baseline.
                result = await self._run_single_starcoder_test(starcoder, test_case, test_name)
                results.append(result)

        finally:
            await starcoder.close()

        return results

    async def _test_pipeline_regression(self) -> List[RegressionTestResult]:
        """Exécute les tests de régression pour le pipeline complet."

        Returns:
            Une liste de `RegressionTestResult` pour les tests de pipeline.
        """
        results = []
        orchestrator = Orchestrator() # Assurez-vous que cette instance est correctement configurée.
        await orchestrator.initialize()

        try:
            sfd_files = Path("tests/regression/fixtures/sample_sfd").glob("*")

            for sfd_file in sfd_files:
                test_name = f"pipeline_{sfd_file.stem}"
                # Exécute le test de pipeline et compare avec la baseline.
                result = await self._run_pipeline_regression_test(orchestrator, sfd_file, test_name)
                results.append(result)

        finally:
            await orchestrator.close()

        return results

    async def _test_performance_regression(self) -> Dict[str, Any]:
        """Exécute les tests de régression de performance."

        Compare les métriques de performance actuelles avec les baselines.

        Returns:
            Un dictionnaire contenant les comparaisons de métriques de performance.
        """
        logger.info("Exécution des tests de régression de performance...")
        baseline_file = self.baseline_path / "performance.json"

        baseline: Dict[str, Any] = {}
        if baseline_file.exists():
            try:
                baseline = json.loads(baseline_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError as e:
                logger.error(f"Erreur de lecture de la baseline de performance {baseline_file}: {e}")

        # Mesure les performances actuelles.
        current_metrics = await self._measure_performance()

        comparisons = {}
        for metric, current_value in current_metrics.items():
            if metric in baseline:
                baseline_value = baseline[metric]
                ratio = current_value / baseline_value if baseline_value != 0 else float('inf')
                status = "PASS"
                if metric.endswith("_time") or metric.endswith("_duration") or metric.endswith("_usage_mb"):
                    # Pour les métriques où une valeur plus petite est meilleure.
                    if ratio > self.config["thresholds"]["max_time_increase"]:
                        status = "FAIL"
                else:
                    # Pour les métriques où une valeur plus grande est meilleure (ex: débit).
                    if ratio < (1 / self.config["thresholds"]["max_time_increase"]):
                        status = "FAIL"

                comparisons[metric] = {
                    "baseline": baseline_value,
                    "current": current_value,
                    "ratio": ratio,
                    "status": status
                }
            else:
                comparisons[metric] = {
                    "current": current_value,
                    "status": "NEW"
                }

        return comparisons

    async def _run_single_qwen3_test(self, qwen3: Qwen3OllamaInterface,
                                     test_case: Dict[str, Any], test_name: str) -> RegressionTestResult:
        """Exécute un test unique pour Qwen3 et compare son résultat avec la baseline."

        Args:
            qwen3: L'instance de l'interface Qwen3.
            test_case: Le dictionnaire du cas de test.
            test_name: Le nom du test.

        Returns:
            Un objet `RegressionTestResult`.
        """
        baseline_file = self.baseline_path / f"{test_name}.json"

        # Exécution actuelle du test Qwen3.
        # Assurez-vous que `analyze_sfd` prend un `SFDAnalysisRequest`.
        from src.models.sfd_models import SFDAnalysisRequest
        sfd_request = SFDAnalysisRequest(content=test_case["input"], extraction_type=test_case.get("extraction_type", "complete"))
        result = await qwen3.analyze_sfd(sfd_request)

        return self._compare_with_baseline(test_name, result, baseline_file)

    async def _run_single_starcoder_test(self, starcoder: StarCoder2OllamaInterface,
                                         test_case: Dict[str, Any], test_name: str) -> RegressionTestResult:
        """Exécute un test unique pour StarCoder2 et compare son résultat avec la baseline."

        Args:
            starcoder: L'instance de l'interface StarCoder2.
            test_case: Le dictionnaire du cas de test.
            test_name: Le nom du test.

        Returns:
            Un objet `RegressionTestResult`.
        """
        baseline_file = self.baseline_path / f"{test_name}.json"

        # Exécution actuelle du test StarCoder2.
        result = await starcoder.generate_playwright_test(
            scenario=test_case["scenario"],
            config=test_case.get("config", {}),
            test_type=TestType.E2E
        )

        return self._compare_with_baseline(test_name, result, baseline_file)

    async def _run_pipeline_regression_test(self, orchestrator: Orchestrator,
                                            sfd_file: Path, test_name: str) -> RegressionTestResult:
        """Exécute un test de régression du pipeline complet et compare son résultat avec la baseline."

        Args:
            orchestrator: L'instance de l'orchestrateur.
            sfd_file: Le chemin vers le fichier SFD à traiter.
            test_name: Le nom du test.

        Returns:
            Un objet `RegressionTestResult`.
        """
        baseline_file = self.baseline_path / f"{test_name}.json"

        # Exécution actuelle du pipeline.
        result = await orchestrator.run_full_pipeline(str(sfd_file))

        return self._compare_with_baseline(test_name, result, baseline_file)

    def _compare_with_baseline(self, test_name: str, current_result: Dict[str, Any],
                               baseline_file: Path) -> RegressionTestResult:
        """Compare les résultats actuels d'un test avec sa baseline."

        Args:
            test_name: Le nom du test.
            current_result: Le dictionnaire des résultats actuels du test.
            baseline_file: Le chemin vers le fichier de baseline.

        Returns:
            Un objet `RegressionTestResult` indiquant le statut du test (PASS, FAIL, NEW).
        """
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "result_hash": hashlib.md5(json.dumps(current_result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        }

        if not baseline_file.exists():
            # Si aucune baseline n'existe, le test est considéré comme nouveau et la baseline est créée.
            logger.info(f"Création d'une nouvelle baseline pour le test : {test_name}")
            baseline_file.write_text(json.dumps(current_result, indent=2, ensure_ascii=False))
            return RegressionTestResult(test_name, "NEW", metrics)

        try:
            baseline = json.loads(baseline_file.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de lecture de la baseline {baseline_file}: {e}. Le test sera marqué comme FAIL.")
            return RegressionTestResult(test_name, "FAIL", metrics, diff=f"Erreur de lecture de la baseline: {e}")

        # Compare les résultats actuels avec la baseline.
        if self._are_results_equivalent(current_result, baseline):
            logger.info(f"Test de régression {test_name} : PASS.")
            return RegressionTestResult(test_name, "PASS", metrics)
        else:
            diff = self._generate_diff(baseline, current_result)
            logger.warning(f"Test de régression {test_name} : FAIL. Différences détectées.")
            return RegressionTestResult(test_name, "FAIL", metrics, diff)

    def _are_results_equivalent(self, current: Dict[str, Any], baseline: Dict[str, Any]) -> bool:
        """Vérifie si deux dictionnaires de résultats sont équivalents."

        Pour l'instant, la comparaison est basée sur le hachage MD5 du JSON sérialisé.
        Une logique de comparaison plus sophistiquée pourrait être ajoutée ici
        pour ignorer certaines différences (ex: horodatages, IDs dynamiques).

        Args:
            current: Le dictionnaire des résultats actuels.
            baseline: Le dictionnaire des résultats de la baseline.

        Returns:
            True si les résultats sont considérés comme équivalents, False sinon.
        """
        current_hash = hashlib.md5(json.dumps(current, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        baseline_hash = hashlib.md5(json.dumps(baseline, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return current_hash == baseline_hash

    def _generate_diff(self, baseline: Dict[str, Any], current: Dict[str, Any]) -> str:
        """Génère un 'diff' lisible entre deux dictionnaires de résultats."

        Args:
            baseline: Le dictionnaire des résultats de la baseline.
            current: Le dictionnaire des résultats actuels.

        Returns:
            Une chaîne de caractères représentant le 'diff' unifié.
        """
        import difflib
        baseline_str = json.dumps(baseline, indent=2, sort_keys=True, ensure_ascii=False).splitlines()
        current_str = json.dumps(current, indent=2, sort_keys=True, ensure_ascii=False).splitlines()

        diff = difflib.unified_diff(
            baseline_str, current_str,
            fromfile='baseline', tofile='current',
            lineterm=''
        )
        return '\n'.join(diff)

    def _load_test_cases(self, model_type: str) -> List[Dict[str, Any]]:
        """Charge les cas de test spécifiques à un type de modèle depuis les fixtures."

        Args:
            model_type: Le type de modèle (ex: 'qwen3', 'starcoder2').

        Returns:
            Une liste de dictionnaires, chaque dictionnaire représentant un cas de test.
        """
        test_cases_dir = Path("tests/regression/fixtures") / model_type
        test_cases: List[Dict[str, Any]] = []

        if not test_cases_dir.exists():
            logger.warning(f"Répertoire de cas de test non trouvé : {test_cases_dir}")
            return []

        for file in test_cases_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    test_cases.extend(json.loads(f.read()))
            except json.JSONDecodeError as e:
                logger.error(f"Erreur de lecture du fichier de cas de test {file}: {e}")
        return test_cases

    async def _measure_performance(self) -> Dict[str, float]:
        """Mesure les métriques de performance actuelles de l'application (stub)."

        Dans une implémentation réelle, cette méthode appellerait des outils
        de profiling ou des endpoints de métriques pour collecter des données
        sur le temps de démarrage, le temps de réponse moyen, l'utilisation mémoire, etc.

        Returns:
            Un dictionnaire de métriques de performance.
        """
        logger.info("Mesure des performances actuelles (stub)...")
        # Implémentation simplifiée pour la démonstration.
        import asyncio
        await asyncio.sleep(1) # Simule un délai de mesure.
        return {
            "startup_time": 2.5,
            "average_response_time": 1.2,
            "memory_usage_mb": 512
        }

    def _generate_regression_report(self, results: Dict[str, Any]):
        """Génère un rapport HTML détaillé des résultats de la régression."

        Args:
            results: Le dictionnaire complet des résultats de la suite de régression.
        """
        report_file = self.results_path / f"regression_report_{datetime.now():%Y%m%d_%H%M%S}.html"

        # Construction du contenu HTML du rapport.
        test_rows_html = []
        for t in results['tests']:
            diff_html = f"<pre>{t.diff}</pre>" if t.diff else ""
            test_rows_html.append(f"""
            <tr>
                <td>{t.test_name}</td>
                <td class='{t.status.lower()}'>{t.status}</td>
                <td>{json.dumps(t.metrics, ensure_ascii=False)}</td>
                <td>{diff_html}</td>
            </tr>
            """)

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Altiora Regression Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .pass {{ color: green; font-weight: bold; }}
        .fail {{ color: red; font-weight: bold; }}
        .new {{ color: blue; font-weight: bold; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }}
        th {{ background-color: #f2f2f2; }}
        pre {{ white-space: pre-wrap; word-wrap: break-word; background-color: #eee; padding: 10px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h1>Rapport de Tests de Régression Altiora</h1>
    <p>Généré le : {results['timestamp']}</p>

    <h2>Résumé</h2>
    <ul>
        <li class="pass">Réussis : {results['summary']['passed']}</li>
        <li class="fail">Échoués : {results['summary']['failed']}</li>
        <li class="new">Nouveaux : {results['summary']['new']}</li>
    </ul>

    <h2>Résultats des Tests</h2>
    <table>
        <thead>
            <tr><th>Test</th><th>Statut</th><th>Métriques</th><th>Différences</th></tr>
        </thead>
        <tbody>
            {''.join(test_rows_html)}
        </tbody>
    </table>

    <h2>Métriques de Performance</h2>
    <pre>{json.dumps(results['performance_metrics'], indent=2, ensure_ascii=False)}</pre>
</body>
</html>
"""
        try:
            report_file.write_text(html_content, encoding='utf-8')
            logger.info(f"Rapport de régression HTML généré : {report_file}")
        except (IOError, OSError) as e:
            logger.error(f"Erreur lors de l'écriture du rapport HTML : {e}")

    async def _update_baselines(self, results: Dict[str, Any]):
        """Met à jour les fichiers de baseline avec les résultats actuels des tests marqués comme 'NEW' ou 'FAIL'."

        Args:
            results: Le dictionnaire complet des résultats de la suite de régression.
        """
        logger.info("Mise à jour des baselines...")
        for test_result in results['tests']:
            if test_result.status == "NEW" or test_result.status == "FAIL":
                baseline_file = self.baseline_path / f"{test_result.test_name}.json"
                try:
                    # Sauvegarde le résultat actuel comme nouvelle baseline.
                    json.dumps(test_result.metrics, indent=2, ensure_ascii=False) # Assurez-vous que c'est le bon contenu à sauvegarder.
                    baseline_file.write_text(json.dumps(test_result.metrics, indent=2, ensure_ascii=False), encoding='utf-8')
                    logger.info(f"Baseline mise à jour pour {test_result.test_name} : {baseline_file}")
                except (IOError, OSError) as e:
                    logger.error(f"Erreur lors de la mise à jour de la baseline {baseline_file}: {e}")


# Configuration pour pytest (pour l'exécution via `pytest tests/regression/test_regression_suite.py`)
@pytest.mark.regression
@pytest.mark.asyncio
async def test_full_regression_suite(wait_for_services):
    """Test de régression complet exécuté par pytest."

    Cette fonction est le point d'entrée pour Pytest. Elle initialise la suite
    de régression et exécute tous les tests définis.
    """
    suite = RegressionSuite()
    results = await suite.run_full_regression()

    # Assertions finales sur le résumé de la régression.
    assert results["summary"]["failed"] == 0, f"Des tests de régression ont échoué : {results['summary']['failed']} échecs."
    assert results["summary"]["passed"] > 0, "Aucun test de régression n'a réussi."
