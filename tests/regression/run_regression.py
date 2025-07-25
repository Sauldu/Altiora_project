#!/usr/bin/env python3
"""Script CLI pour lancer les tests de régression de l'application Altiora.

Ce script permet d'exécuter la suite complète des tests de régression.
Il peut être configuré pour mettre à jour les baselines (références) des tests,
ainsi que pour générer un rapport détaillé des résultats. Il s'assure également
que les répertoires nécessaires et les données d'exemple sont en place.

Utilisation:
    python run_regression.py [--update-baselines] [--report] [--verbose]
"""

import argparse
import asyncio
import logging
import json
from pathlib import Path

from tests.regression.test_regression_suite import RegressionSuite # Assurez-vous que ce module existe et est correct.

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Fonction principale pour exécuter la suite de tests de régression."

    Parse les arguments de la ligne de commande pour configurer l'exécution des tests.
    """
    parser = argparse.ArgumentParser(description="Exécute les tests de régression Altiora.")
    parser.add_argument("--update-baselines", action="store_true",
                        help="Met à jour les fichiers de référence (baselines) avec les résultats actuels.")
    parser.add_argument("--report", action="store_true",
                        help="Génère un rapport HTML détaillé des résultats de régression.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Active la sortie verbeuse pour un débogage plus détaillé.")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Crée les répertoires nécessaires pour les baselines et les résultats des tests.
    Path("tests/regression/baselines").mkdir(parents=True, exist_ok=True)
    Path("tests/regression/results").mkdir(parents=True, exist_ok=True)
    Path("tests/regression/fixtures/sample_sfd").mkdir(parents=True, exist_ok=True)

    # Crée les fichiers de test exemple s'ils n'existent pas, pour assurer un environnement de test fonctionnel.
    await _create_sample_fixtures()

    # Initialise la suite de régression.
    suite = RegressionSuite()
    suite.config["update_baselines"] = args.update_baselines
    suite.config["generate_report"] = args.report # Passe l'option de rapport à la suite.

    logger.info("🚀 Démarrage des tests de régression...")
    results = await suite.run_full_regression()

    # Affichage du résumé des résultats des tests de régression.
    print("\n" + "=" * 60)
    logger.info("📊 RÉSUMÉ DES TESTS DE RÉGRESSION")
    print("=" * 60)
    logger.info(f"Tests totaux : {len(results['tests'])}")
    logger.info(f"✅ Réussis : {results['summary']['passed']}")
    logger.info(f"❌ Échoués : {results['summary']['failed']}")
    logger.info(f"🆕 Nouveaux : {results['summary']['new']}")

    if results["summary"]["failed"] > 0:
        logger.info("\n⚠️  Certains tests ont échoué - veuillez consulter le rapport détaillé pour plus d'informations.")
        exit(1) # Quitte avec un code d'erreur si des tests ont échoué.
    else:
        logger.info("\n🎉 Tous les tests de régression ont réussi !")


async def _create_sample_fixtures():
    """Crée des fichiers de fixtures de test exemple pour la suite de régression."

    Ces fichiers sont utilisés pour simuler des entrées pour les tests
    (ex: spécifications SFD, cas de test Qwen3/StarCoder2).
    """
    fixtures_dir = Path("tests/regression/fixtures")
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # Fichiers SFD d'exemple.
    sample_sfd_dir = fixtures_dir / "sample_sfd"
    sample_sfd_dir.mkdir(parents=True, exist_ok=True)

    login_spec_path = sample_sfd_dir / "login_spec.txt"
    if not login_spec_path.exists():
        login_spec_path.write_text("""
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
        logger.info(f"Fichier SFD d'exemple créé : {login_spec_path}")

    # Cas de test Qwen3.
    qwen3_dir = fixtures_dir / "qwen3"
    qwen3_dir.mkdir(parents=True, exist_ok=True)

    extraction_test_path = qwen3_dir / "test_cases.json"
    if not extraction_test_path.exists():
        extraction_test_path.write_text(json.dumps([
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
        logger.info(f"Fichier de cas de test Qwen3 créé : {extraction_test_path}")

    # Cas de test StarCoder2.
    starcoder2_dir = fixtures_dir / "starcoder2"
    starcoder2_dir.mkdir(parents=True, exist_ok=True)

    starcoder_test_path = starcoder2_dir / "test_cases.json"
    if not starcoder_test_path.exists():
        starcoder_test_path.write_text(json.dumps([
            {
                "name": "basic_playwright_test",
                "scenario": {
                    "titre": "Test de connexion",
                    "objectif": "Vérifier la connexion",
                    "etapes": ["Naviguer vers /login", "Cliquer sur connexion"]
                }
            }
        ], indent=2))
        logger.info(f"Fichier de cas de test StarCoder2 créé : {starcoder_test_path}")


if __name__ == "__main__":
    asyncio.run(main())