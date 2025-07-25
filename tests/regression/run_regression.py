#!/usr/bin/env python3
"""
Script CLI pour lancer les tests de régression
Usage:
    python run_regression.py [--update-baselines] [--report] [--verbose]
"""

import argparse
import asyncio
import logging
from pathlib import Path

from test_regression_suite import RegressionSuite

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Run Altiora regression tests")
    parser.add_argument("--update-baselines", action="store_true",
                        help="Update baseline files with current results")
    parser.add_argument("--report", action="store_true",
                        help="Generate detailed HTML report")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Créer les répertoires nécessaires
    Path("tests/regression/baselines").mkdir(parents=True, exist_ok=True)
    Path("tests/regression/results").mkdir(parents=True, exist_ok=True)
    Path("tests/regression/fixtures/sample_sfd").mkdir(parents=True, exist_ok=True)

    # Créer les fichiers de test exemple s'ils n'existent pas
    await _create_sample_fixtures()

    # Lancer la suite
    suite = RegressionSuite()
    suite.config["update_baselines"] = args.update_baselines

    logger.info("🚀 Starting regression tests...")
    results = await suite.run_full_regression()

    # Affichage résumé
    print("\n" + "=" * 60)
    logger.info("📊 REGRESSION TEST SUMMARY")
    print("=" * 60)
    logger.info(f"Total tests: {len(results['tests'])}")
    logger.info(f"✅ Passed: {results['summary']['passed']}")
    logger.info(f"❌ Failed: {results['summary']['failed']}")
    logger.info(f"🆕 New: {results['summary']['new']}")

    if results["summary"]["failed"] > 0:
        logger.info("\n⚠️  Some tests failed - check the detailed report")
        exit(1)
    else:
        logger.info("\n🎉 All regression tests passed!")


async def _create_sample_fixtures():
    """Crée des fixtures de test exemple"""
    fixtures_dir = Path("tests/regression/fixtures")

    # Sample SFD files
    sample_sfd_dir = fixtures_dir / "sample_sfd"

    login_spec = sample_sfd_dir / "login_spec.txt"
    if not login_spec.exists():
        login_spec.parent.mkdir(parents=True, exist_ok=True)
        login_spec.write_text("""
Spécification Fonctionnelle - Module de Connexion

Objectif: Permettre aux utilisateurs de s'authentifier sur la plateforme

Scénario 1: Connexion réussie
- Pré-condition: L'utilisateur a un compte actif
- Étapes:
  1. Naviguer vers /login
  2. Saisir email valide: user@example.com
  3. Saisir mot de passe valide: SecurePass123!
  4. Cliquer sur "Se connecter"
- Résultat attendu: Redirection vers /dashboard avec message "Bienvenue"

Scénario 2: Email invalide
- Étapes:
  1. Naviguer vers /login
  2. Saisir email invalide: invalid-email
  3. Saisir mot de passe: anything
  4. Cliquer sur "Se connecter"
- Résultat attendu: Message d'erreur "Format email invalide"
""")

    # Qwen3 test cases
    qwen3_dir = fixtures_dir / "qwen3"
    qwen3_dir.mkdir(parents=True, exist_ok=True)

    extraction_test = qwen3_dir / "test_cases.json"
    if not extraction_test.exists():
        extraction_test.write_text(json.dumps([
            {
                "name": "basic_extraction",
                "input": "Test de connexion avec email et mot de passe",
                "expected_scenarios": 1
            },
            {
                "name": "complex_extraction",
                "input": "Spécification avec plusieurs scénarios de test",
                "expected_scenarios": 3
            }
        ], indent=2))

    # StarCoder2 test cases
    starcoder2_dir = fixtures_dir / "starcoder2"
    starcoder2_dir.mkdir(parents=True, exist_ok=True)

    starcoder_test = starcoder2_dir / "test_cases.json"
    if not starcoder_test.exists():
        starcoder_test.write_text(json.dumps([
            {
                "name": "basic_playwright_test",
                "scenario": {
                    "titre": "Test de connexion",
                    "objectif": "Vérifier la connexion",
                    "etapes": ["Naviguer vers /login", "Cliquer sur connexion"]
                }
            }
        ], indent=2))


if __name__ == "__main__":
    asyncio.run(main())