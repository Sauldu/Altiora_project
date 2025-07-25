#!/usr/bin/env python3
"""Script d'installation et de configuration en un clic pour le projet Altiora.

Ce script automatise la mise en place de l'environnement de développement
et de production d'Altiora. Il gère la vérification des prérequis système,
la création d'un environnement virtuel Python, l'installation des dépendances,
la configuration des variables d'environnement, la création des répertoires
nécessaires, le téléchargement des modèles Ollama et la vérification des services.

Il est conçu pour être idempotent, c'est-à-dire qu'il peut être exécuté
plusieurs fois sans causer d'effets secondaires indésirables.
"""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List
import logging

from configs.config_module import get_settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AltioraSetup:
    """Installateur idempotent pour le projet Altiora."""

    def __init__(self, base_dir: Path = Path.cwd()) -> None:
        """Initialise l'installateur."

        Args:
            base_dir: Le répertoire de base du projet (par défaut, le répertoire courant).
        """
        self.base_dir = base_dir
        self.venv_path = base_dir / ".venv"
        self.python_min = (3, 8)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.successes: List[str] = []
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # Flux d'exécution principal
    # ------------------------------------------------------------------
    def run(self, *, skip_services: bool = False, dev_mode: bool = False) -> None:
        """Exécute le processus d'installation complet."

        Args:
            skip_services: Si True, saute le téléchargement des modèles Ollama et la vérification des services.
            dev_mode: Si True, installe les dépendances de développement.
        """
        logger.info("🚀 Démarrage de l'installateur Altiora")
        print("=" * 60)

        self.check_python_version()
        self.check_system_requirements()
        self.setup_virtual_environment()
        self.install_dependencies(dev_mode)
        self.setup_environment()
        self.create_directories()
        if not skip_services:
            self.setup_ollama_models()
            self.check_services()
        self.init_database()
        self.print_summary()

    # ------------------------------------------------------------------
    # Vérifications des prérequis
    # ------------------------------------------------------------------
    def check_python_version(self) -> None:
        """Vérifie que la version de Python installée est compatible."

        Si la version est inférieure à `self.python_min`, une erreur est ajoutée et le script s'arrête.
        """
        if sys.version_info < self.python_min:
            self.errors.append(
                f"Version de Python insuffisante. Python ≥ {'.'.join(map(str, self.python_min))} est requis. Version actuelle : {'.'.join(map(str, sys.version_info[:3]))}"
            )
            sys.exit(1)
        self.successes.append(f"Version de Python {'.'.join(map(str, sys.version_info[:2]))} ✓")

    def check_system_requirements(self) -> None:
        """Vérifie la présence des outils système nécessaires (Git, Docker)."

        Des avertissements sont ajoutés si les outils ne sont pas trouvés.
        """
        tools = [("Git", "git"), ("Docker", "docker")]
        for name, cmd in tools:
            if shutil.which(cmd):
                self.successes.append(f"{name} ✓")
            else:
                self.warnings.append(f"{name} non trouvé. Veuillez l'installer pour une fonctionnalité complète.")

    # ------------------------------------------------------------------
    # Environnement virtuel
    # ------------------------------------------------------------------
    def setup_virtual_environment(self) -> None:
        """Crée et configure l'environnement virtuel Python du projet."

        Si l'environnement virtuel existe déjà, il n'est pas recréé.
        """
        import venv  # Le module `venv` fait partie de la bibliothèque standard de Python.

        if not self.venv_path.exists():
            logger.info(f"Création de l'environnement virtuel dans {self.venv_path}...")
            venv.create(self.venv_path, with_pip=True)
            self.successes.append("Environnement virtuel créé ✓")
        else:
            self.successes.append("Environnement virtuel déjà existant ✓")

        self._write_activation_script()

    def _write_activation_script(self) -> None:
        """Écrit un script d'activation simple pour l'environnement virtuel."

        Cela facilite l'activation de l'environnement virtuel pour l'utilisateur.
        """
        if platform.system() == "Windows":
            script = self.base_dir / "activate.bat"
            script.write_text(
                f"@echo off\ncall {self.venv_path}\Scripts\activate.bat\necho Environnement virtuel activé.\n"
            )
        else:
            script = self.base_dir / "activate.sh"
            script.write_text(
                f'#!/bin/bash\nsource {self.venv_path}/bin/activate\necho Environnement virtuel activé.\n'
            )
            script.chmod(0o755) # Rend le script exécutable.
        self.successes.append(f"Script d'activation créé ({script.name}) ✓")

    # ------------------------------------------------------------------
    # Dépendances
    # ------------------------------------------------------------------
    def install_dependencies(self, dev: bool) -> None:
        """Installe les dépendances Python du projet."

        Args:
            dev: Si True, installe également les dépendances de développement depuis `requirements-dev.txt`.
        """
        logger.info("Installation des dépendances Python...")
        pip_command = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        if dev:
            pip_command.extend(["-r", "requirements-dev.txt"])

        try:
            subprocess.run(pip_command, check=True, capture_output=True, text=True)
            self.successes.append("Dépendances Python installées ✓")
        except subprocess.CalledProcessError as e:
            self.errors.append(f"Échec de l'installation des dépendances Python : {e.stderr}")
            return

        # Installe les navigateurs Playwright si Playwright est une dépendance.
        if "playwright" in Path("requirements.txt").read_text():
            logger.info("Installation des navigateurs Playwright...")
            try:
                subprocess.run(["playwright", "install", "chromium"], check=True, capture_output=True, text=True)
                self.successes.append("Navigateur Playwright (Chromium) installé ✓")
            except subprocess.CalledProcessError as e:
                self.errors.append(f"Échec de l'installation des navigateurs Playwright : {e.stderr}")

    # ------------------------------------------------------------------
    # Environnement et répertoires
    # ------------------------------------------------------------------
    def setup_environment(self) -> None:
        """Configure le fichier d'environnement `.env` et injecte la clé secrète JWT."

        Si `.env` n'existe pas, il est créé à partir de `.env.example`.
        """
        env_src = self.base_dir / ".env.example"
        env_dst = self.base_dir / ".env"

        if env_src.exists() and not env_dst.exists():
            logger.info(f"Création du fichier .env à partir de {env_src.name}...")
            env_dst.write_text(env_src.read_text())
            self._inject_jwt_secret(env_dst)
            self.successes.append("Fichier .env créé et configuré ✓")
        elif env_dst.exists():
            logger.info("Fichier .env déjà existant. Vérification de la clé JWT...")
            self._inject_jwt_secret(env_dst)
            self.successes.append("Fichier .env existant (clé JWT vérifiée) ✓")
        else:
            self.warnings.append("Ni .env ni .env.example trouvés. Veuillez créer un fichier .env manuellement.")

    @staticmethod
    def _inject_jwt_secret(env_file: Path) -> None:
        """Injecte une clé secrète JWT aléatoire dans le fichier .env si elle n'est pas déjà définie."

        Args:
            env_file: Le chemin vers le fichier `.env`.
        """
        import secrets

        content = env_file.read_text()
        # Vérifie si le placeholder de la clé secrète est présent.
        if "JWT_SECRET_KEY=your-secret-key-here" in content:
            key = secrets.token_urlsafe(32) # Génère une clé sécurisée.
            new_content = content.replace("JWT_SECRET_KEY=your-secret-key-here", f"JWT_SECRET_KEY={key}")
            env_file.write_text(new_content)
            logger.info("Clé JWT_SECRET_KEY injectée dans .env ✓")
        elif "JWT_SECRET_KEY=" not in content:
            # Si la clé n'est pas présente du tout, l'ajoute.
            key = secrets.token_urlsafe(32)
            with open(env_file, "a") as f:
                f.write(f"\nJWT_SECRET_KEY={key}\n")
            logger.info("Clé JWT_SECRET_KEY ajoutée à .env ✓")
        else:
            logger.info("Clé JWT_SECRET_KEY déjà présente dans .env ✓")

    def create_directories(self) -> None:
        """Crée les répertoires nécessaires pour le projet."

        Utilise les chemins définis dans la configuration de l'application.
        """
        logger.info("Création des répertoires nécessaires...")
        # Liste des répertoires à créer.
        dirs_to_create = [
            self.settings.data_dir,
            self.settings.models_dir,
            self.settings.logs_dir,
            self.settings.reports_dir,
            self.settings.temp_dir,
            self.base_dir / "workspace", # Répertoire de travail pour les exécutions.
            self.base_dir / "screenshots", # Pour les captures d'écran des tests.
            self.base_dir / "videos", # Pour les enregistrements vidéo des tests.
            self.base_dir / "artifacts", # Pour les artefacts générés.
        ]
        for d in dirs_to_create:
            d.mkdir(parents=True, exist_ok=True)
        self.successes.append("Répertoires créés ✓")

    # ------------------------------------------------------------------
    # Ollama et services
    # ------------------------------------------------------------------
    def setup_ollama_models(self) -> None:
        """Télécharge les modèles Ollama requis par l'application."

        Les modèles sont définis dans la configuration de l'application.
        """
        logger.info("Téléchargement des modèles Ollama...")
        # Récupère les noms des modèles à partir de la configuration.
        models_to_pull = [model_config.base_model for model_config in self.settings.models.values()]
        
        if not models_to_pull:
            self.warnings.append("Aucun modèle Ollama configuré à télécharger.")
            return

        for model in models_to_pull:
            try:
                logger.info(f"  - Pulling {model}...")
                subprocess.run(["ollama", "pull", model], check=True, capture_output=True, text=True)
                self.successes.append(f"Modèle Ollama {model} téléchargé ✓")
            except FileNotFoundError:
                self.errors.append("La commande `ollama` n'a pas été trouvée. Assurez-vous qu'Ollama est installé et dans le PATH.")
                return # Arrête si ollama n'est pas trouvé.
            except subprocess.CalledProcessError as e:
                self.errors.append(f"Échec du téléchargement du modèle Ollama {model}: {e.stderr}")

    def check_services(self) -> None:
        """Vérifie la disponibilité des services externes (Redis, Ollama, microservices)."

        Des avertissements sont ajoutés si un service n'est pas joignable.
        """
        logger.info("Vérification des services externes...")
        services_to_check = [
            ("Redis", ["redis-cli", "ping"], "PONG"),
            ("Ollama", ["curl", "-s", "http://localhost:11434/api/tags"], "models"), # Vérifie un endpoint Ollama.
            ("Service OCR", ["curl", "-s", "http://localhost:8001/health"], "healthy"),
            ("Service ALM", ["curl", "-s", "http://localhost:8002/health"], "healthy"),
            ("Service Excel", ["curl", "-s", "http://localhost:8003/health"], "healthy"),
            ("Service Playwright", ["curl", "-s", "http://localhost:8004/health"], "healthy"),
        ]
        for name, cmd_args, expected_output_part in services_to_check:
            try:
                result = subprocess.run(cmd_args, check=True, capture_output=True, text=True, timeout=5)
                if expected_output_part in result.stdout or expected_output_part in result.stderr:
                    self.successes.append(f"{name} ✓")
                else:
                    self.warnings.append(f"{name} joignable mais réponse inattendue.")
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
                self.warnings.append(f"{name} non joignable ou erreur : {e}")
            except Exception as e:
                self.warnings.append(f"{name} : Erreur inattendue lors de la vérification : {e}")

    def init_database(self) -> None:
        """Initialise la base de données (stub pour l'instant)."

        Dans cette version, il n'y a pas de base de données SQL directe configurée,
        uniquement Redis. Cette méthode est un placeholder pour une future intégration.
        """
        self.successes.append("Initialisation de la base de données (pas de DB SQL configurée, seulement Redis) ✓")

    # ------------------------------------------------------------------
    # Résumé
    # ------------------------------------------------------------------
    def print_summary(self) -> None:
        """Affiche un résumé des résultats de l'installation."

        Liste les succès, les avertissements et les erreurs.
        """
        print("\n" + "=" * 60)
        logger.info("📊 Résumé de l'installation Altiora")
        print("=" * 60)

        for label, items in (
                ("✅ Succès", self.successes),
                ("⚠️ Avertissements", self.warnings),
                ("❌ Erreurs", self.errors),
        ):
            if items:
                logger.info(f"{label} ({len(items)})")
                for item in items:
                    logger.info(f"   • {item}")
        if self.errors:
            logger.error("\nL'installation a échoué en raison des erreurs ci-dessus. Veuillez les corriger.")
            sys.exit(1)
        else:
            logger.info("\n🎉 Installation terminée avec succès (avec avertissements si présents) !")


# ------------------------------------------------------------------
# Point d'entrée du script
# ------------------------------------------------------------------
def main() -> None:
    """Fonction principale pour exécuter le script d'installation."

    Parse les arguments de la ligne de commande et lance le processus d'installation.
    """
    parser = argparse.ArgumentParser(description="Installateur Altiora.")
    parser.add_argument("--skip-services", action="store_true", help="Ne pas télécharger les modèles Ollama ni vérifier les services.")
    parser.add_argument("--dev", action="store_true", help="Installer les dépendances de développement.")
    args = parser.parse_args()

    # Vérifie que le script est exécuté depuis la racine du projet.
    if not (Path("requirements.txt").exists() and Path("configs").exists()):
        logger.error("❌ Veuillez exécuter ce script depuis la racine du répertoire du projet Altiora.")
        sys.exit(1)

    AltioraSetup().run(skip_services=args.skip_services, dev_mode=args.dev)


if __name__ == "__main__":
    main()