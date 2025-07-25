# cli/commands/doctor.py
"""Commande `doctor` pour la CLI Altiora.

Ce module fournit un outil de diagnostic complet pour vérifier l'état de
l'environnement du projet Altiora. Il effectue des vérifications sur la
version de Python, les dépendances installées, la disponibilité de Docker,
la présence des fichiers et dossiers essentiels, et la configuration des
variables d'environnement critiques.
"""

import os
import subprocess
import sys
from pathlib import Path
import click
import pkg_resources
import logging

logger = logging.getLogger(__name__)


@click.command()
def doctor():
    """Effectue un diagnostic complet de l'environnement du projet Altiora."

    Cette commande vérifie les prérequis système et les configurations clés
    pour s'assurer que le projet peut fonctionner correctement. Elle affiche
    un résumé des vérifications réussies et des problèmes détectés.
    """
    ok = True
    click.echo("🔍 Altiora Doctor – Démarrage du diagnostic…\n")

    # 1. Vérification de la version de Python.
    v = sys.version_info
    if v < (3, 9):
        click.echo(f"❌ Python >= 3.9 requis (actuel {v.major}.{v.minor}).")
        ok = False
    else:
        click.echo("✅ Version de Python compatible.")

    # 2. Vérification des dépendances Python installées.
    try:
        # Tente de charger les dépendances listées dans requirements.txt.
        pkg_resources.require(open("requirements.txt").readlines())
        click.echo("✅ Dépendances Python installées.")
    except Exception as e:
        click.echo(f"❌ Dépendances Python manquantes ou incorrectes : {e}. Exécutez `pip install -r requirements.txt`.")
        ok = False

    # 3. Vérification de la disponibilité de Docker.
    # `docker info` est utilisé pour vérifier si le démon Docker est en cours d'exécution.
    if subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        click.echo("❌ Docker non disponible ou non démarré. Veuillez installer Docker Desktop ou démarrer le service Docker.")
        ok = False
    else:
        click.echo("✅ Docker est disponible.")

    # 4. Vérification des fichiers et dossiers obligatoires du projet.
    click.echo("Vérification de l'arborescence du projet...")
    required_paths = ["src", "configs", "docker-compose.yml", "requirements.txt"]
    for p in required_paths:
        if not Path(p).exists():
            click.echo(f"❌ Fichier/dossier manquant : `{p}`. Assurez-vous d'être à la racine du projet.")
            ok = False
    if ok: # Si aucune erreur n'a été détectée jusqu'à présent pour les chemins.
        click.echo("✅ Arborescence du projet conforme.")

    # 5. Vérification des variables d'environnement critiques.
    click.echo("Vérification des variables d'environnement critiques...")
    required_env_vars = ("JWT_SECRET_KEY", "ENCRYPTION_KEY")
    missing_env_vars = [k for k in required_env_vars if not os.getenv(k)]
    if missing_env_vars:
        click.echo(f"❌ Variables d'environnement manquantes : {', '.join(missing_env_vars)}. Exécutez `python scripts/generate_keys.py`.")
        ok = False
    else:
        click.echo("✅ Variables d'environnement critiques configurées.")

    # Affichage du résumé final.
    click.echo("\n" + ("✅ Tout semble OK ! Votre environnement Altiora est prêt." if ok else "❌ Des erreurs ont été détectées. Veuillez consulter les messages ci-dessus pour les corriger."))
    if not ok:
        sys.exit(1) # Quitte avec un code d'erreur si des problèmes sont détectés.


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Pour tester ce script, vous pouvez simuler des conditions d'erreur
    # en modifiant temporairement les variables d'environnement ou les fichiers.

    print("\n--- Lancement de la démonstration du Altiora Doctor ---")
    try:
        # Simule un environnement valide pour le premier run.
        # Assurez-vous que `requirements.txt` et `docker-compose.yml` existent.
        # Et que `JWT_SECRET_KEY` et `ENCRYPTION_KEY` sont définis dans votre `.env` ou environnement.
        doctor() 
    except SystemExit as e:
        print(f"Démonstration terminée avec le code de sortie : {e.code}")

    # Exemple de simulation d'un échec (décommenter pour tester).
    # print("\n--- Simulation d'un échec (Python version) ---")
    # original_version_info = sys.version_info
    # sys.version_info = (3, 7, 0, 'final', 0) # Simule une version Python trop ancienne.
    # try:
    #     doctor()
    # except SystemExit as e:
    #     print(f"Démonstration terminée avec le code de sortie : {e.code}")
    # finally:
    #     sys.version_info = original_version_info # Restaure la version.

    # print("\n--- Simulation d'un échec (variable d'environnement manquante) ---")
    # original_jwt_secret = os.getenv("JWT_SECRET_KEY")
    # if "JWT_SECRET_KEY" in os.environ: del os.environ["JWT_SECRET_KEY"]
    # try:
    #     doctor()
    # except SystemExit as e:
    #     print(f"Démonstration terminée avec le code de sortie : {e.code}")
    # finally:
    #     if original_jwt_secret: os.environ["JWT_SECRET_KEY"] = original_jwt_secret

    print("Démonstration du Altiora Doctor terminée.")