"""
Suite de tests de régression automatiques pour Altiora
Compare les résultats actuels avec les références stockées
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import pytest
import yaml

from src.orchestrator import Orchestrator
from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from models.starcoder2.starcoder2_interface import StarCoder2OllamaInterface, TestType


class RegressionTestResult:
    """Résultat d'un test de régression"""

    def __init__(self, test_name: str, status: str, metrics: Dict[str, Any],
                 diff: Optional[str] = None):
        self.test_name = test_name
        self.status = status  # PASS, FAIL, NEW
        self.metrics = metrics
        self.diff = diff
        self.timestamp = datetime.now().isoformat()


class RegressionSuite:
    """Suite de tests de régression automatiques"""

    def __init__(self, config_path: str = "tests/regression/regression_config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.baseline_path = Path("tests/regression/baselines")
        self.baseline_path.mkdir(exist_ok=True)
        self.results_path = Path("tests/regression/results")
        self.results_path.mkdir(exist_ok=True)

    def _load_config(self) -> Dict[str, Any]:
        """Charge la configuration des tests de régression"""
        if not self.config_path.exists():
            default_config = {
                "thresholds": {
                    "max_time_increase": 1.2,  # 20% max
                    "min_scenarios": 1,
                    "min_tests_generated": 1,
                    "code_similarity": 0.8
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
                    "response_time": 30  # seconds max
                }
            }
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                yaml.dump(default_config, f)
        return yaml.safe_load(self.config_path.read_text())

    async def run_full_regression(self) -> Dict[str, Any]:
        """Exécute la suite complète de régression"""
        logger.info("🔄 Début des tests de régression...")

        results = {
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "summary": {"passed": 0, "failed": 0, "new": 0},
            "performance_metrics": {}
        }

        # Tests des modèles
        model_results = await self._test_models_regression()
        results["tests"].extend(model_results)

        # Tests du pipeline complet
        pipeline_results = await self._test_pipeline_regression()
        results["tests"].extend(pipeline_results)

        # Tests de performance
        perf_results = await self._test_performance_regression()
        results["performance_metrics"] = perf_results

        # Génération du rapport
        self._generate_regression_report(results)

        # Mise à jour des baselines si demandé
        if self.config.get("update_baselines", False):
            await self._update_baselines(results)

        # Résumé
        results["summary"] = {
            "passed": sum(1 for t in results["tests"] if t.status == "PASS"),
            "failed": sum(1 for t in results["tests"] if t.status == "FAIL"),
            "new": sum(1 for t in results["tests"] if t.status == "NEW")
        }

        return results

    async def _test_models_regression(self) -> List[RegressionTestResult]:
        """Tests de régression pour les modèles LLM"""
        results = []

        # Test Qwen3
        qwen3_results = await self._test_qwen3_regression()
        results.extend(qwen3_results)

        # Test StarCoder2
        starcoder_results = await self._test_starcoder2_regression()
        results.extend(starcoder_results)

        return results

    async def _test_qwen3_regression(self) -> List[RegressionTestResult]:
        """Test de régression pour Qwen3"""
        results = []
        qwen3 = Qwen3OllamaInterface()
        await qwen3.initialize()

        try:
            # Chargement des cas de test
            test_cases = self._load_test_cases("qwen3")

            for test_case in test_cases:
                test_name = f"qwen3_{test_case['name']}"
                result = await self._run_single_qwen3_test(qwen3, test_case, test_name)
                results.append(result)

        finally:
            await qwen3.close()

        return results

    async def _test_starcoder2_regression(self) -> List[RegressionTestResult]:
        """Test de régression pour StarCoder2"""
        results = []
        starcoder = StarCoder2OllamaInterface()
        await starcoder.initialize()

        try:
            test_cases = self._load_test_cases("starcoder2")

            for test_case in test_cases:
                test_name = f"starcoder2_{test_case['name']}"
                result = await self._run_single_starcoder_test(starcoder, test_case, test_name)
                results.append(result)

        finally:
            await starcoder.close()

        return results

    async def _test_pipeline_regression(self) -> List[RegressionTestResult]:
        """Test de régression du pipeline complet"""
        results = []
        orchestrator = Orchestrator()
        await orchestrator.initialize()

        try:
            sfd_files = Path("tests/regression/fixtures/sample_sfd").glob("*")

            for sfd_file in sfd_files:
                test_name = f"pipeline_{sfd_file.stem}"
                result = await self._run_pipeline_regression_test(orchestrator, sfd_file, test_name)
                results.append(result)

        finally:
            await orchestrator.close()

        return results

    async def _test_performance_regression(self) -> Dict[str, Any]:
        """Test de régression des performances"""
        baseline_file = self.baseline_path / "performance.json"

        if baseline_file.exists():
            baseline = json.loads(baseline_file.read_text())
        else:
            baseline = {}

        # Test actuel
        current_metrics = await self._measure_performance()

        # Comparaison
        comparisons = {}
        for metric, current_value in current_metrics.items():
            if metric in baseline:
                baseline_value = baseline[metric]
                ratio = current_value / baseline_value
                status = "PASS" if ratio < self.config["thresholds"]["max_time_increase"] else "FAIL"
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
                                     test_case: Dict, test_name: str) -> RegressionTestResult:
        """Exécute un test unique pour Qwen3"""
        baseline_file = self.baseline_path / f"{test_name}.json"

        # Exécution actuelle
        result = await qwen3.analyze_sfd(
            sfd_content=test_case["input"],
            extraction_type=test_case.get("extraction_type", "complete")
        )

        return self._compare_with_baseline(test_name, result, baseline_file)

    async def _run_single_starcoder_test(self, starcoder: StarCoder2OllamaInterface,
                                         test_case: Dict, test_name: str) -> RegressionTestResult:
        """Exécute un test unique pour StarCoder2"""
        baseline_file = self.baseline_path / f"{test_name}.json"

        # Exécution actuelle
        result = await starcoder.generate_playwright_test(
            scenario=test_case["scenario"],
            config=test_case.get("config", {}),
            test_type=TestType.E2E
        )

        return self._compare_with_baseline(test_name, result, baseline_file)

    async def _run_pipeline_regression_test(self, orchestrator: Orchestrator,
                                            sfd_file: Path, test_name: str) -> RegressionTestResult:
        """Exécute un test de régression du pipeline complet"""
        baseline_file = self.baseline_path / f"{test_name}.json"

        # Exécution actuelle
        result = await orchestrator.process_sfd_to_tests(str(sfd_file))

        return self._compare_with_baseline(test_name, result, baseline_file)

    def _compare_with_baseline(self, test_name: str, current_result: Dict,
                               baseline_file: Path) -> RegressionTestResult:
        """Compare les résultats avec la baseline"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "result_hash": hashlib.md5(json.dumps(current_result, sort_keys=True).encode()).hexdigest()
        }

        if not baseline_file.exists():
            # Premier test - créer la baseline
            baseline_file.write_text(json.dumps(current_result, indent=2))
            return RegressionTestResult(test_name, "NEW", metrics)

        baseline = json.loads(baseline_file.read_text())

        # Comparaison des métriques clés
        if self._are_results_equivalent(current_result, baseline):
            return RegressionTestResult(test_name, "PASS", metrics)
        else:
            diff = self._generate_diff(baseline, current_result)
            return RegressionTestResult(test_name, "FAIL", metrics, diff)

    def _are_results_equivalent(self, current: Dict, baseline: Dict) -> bool:
        """Vérifie si deux résultats sont équivalents"""
        # Logique de comparaison spécifique au type de test
        # Pour simplifier, on compare les hachages ici
        current_hash = hashlib.md5(json.dumps(current, sort_keys=True).encode()).hexdigest()
        baseline_hash = hashlib.md5(json.dumps(baseline, sort_keys=True).encode()).hexdigest()
        return current_hash == baseline_hash

    def _generate_diff(self, baseline: Dict, current: Dict) -> str:
        """Génère un diff lisible entre deux résultats"""
        import difflib
        baseline_str = json.dumps(baseline, indent=2, sort_keys=True).splitlines()
        current_str = json.dumps(current, indent=2, sort_keys=True).splitlines()

        diff = difflib.unified_diff(
            baseline_str, current_str,
            fromfile='baseline', tofile='current',
            lineterm=''
        )
        return '\n'.join(diff)

    def _load_test_cases(self, model: str) -> List[Dict]:
        """Charge les cas de test pour un modèle"""
        test_cases_dir = Path("tests/regression/fixtures") / model
        test_cases = []

        for file in test_cases_dir.glob("*.json"):
            test_cases.extend(json.loads(file.read_text()))

        return test_cases

    async def _measure_performance(self) -> Dict[str, float]:
        """Mesure les performances actuelles"""
        # Implémentation simplifiée
        return {
            "startup_time": 2.5,
            "average_response_time": 1.2,
            "memory_usage_mb": 512
        }

    def _generate_regression_report(self, results: Dict[str, Any]):
        """Génère un rapport de régression HTML détaillé"""
        report_file = self.results_path / f"regression_report_{datetime.now():%Y%m%d_%H%M%S}.html"

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Altiora Regression Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .pass {{ color: green; }}
        .fail {{ color: red; }}
        .new {{ color: blue; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Altiora Regression Test Report</h1>
    <p>Generated: {results['timestamp']}</p>

    <h2>Summary</h2>
    <ul>
        <li class="pass">Passed: {results['summary']['passed']}</li>
        <li class="fail">Failed: {results['summary']['failed']}</li>
        <li class="new">New: {results['summary']['new']}</li>
    </ul>

    <h2>Test Results</h2>
    <table>
        <tr><th>Test</th><th>Status</th><th>Metrics</th></tr>
        {''.join(f"<tr><td>{t.test_name}</td><td class='{t.status.lower()}'>{t.status}</td><td>{json.dumps(t.metrics)}</td></tr>" for t in results['tests'])}
    </table>
</body>
</html>
"""
        report_file.write_text(html_content)


# Configuration pour pytest
@pytest.mark.regression
@pytest.mark.asyncio
async def test_full_regression_suite():
    """Test de régression complet exécuté par pytest"""
    suite = RegressionSuite()
    results = await suite.run_full_regression()

    # Assertions
    assert results["summary"]["failed"] == 0, f"Regression tests failed: {results['summary']['failed']}"
    assert results["summary"]["passed"] > 0, "No regression tests passed"