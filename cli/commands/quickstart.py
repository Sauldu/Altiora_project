# cli/commands/quickstart.py
"""Commande `quickstart` pour la CLI Altiora.

Ce module fournit un assistant interactif pour configurer rapidement un projet Altiora.
Il guide l'utilisateur à travers les étapes de clonage du projet (si nécessaire),
la configuration des variables d'environnement, la construction des images Docker,
et le lancement des services.
"""

import os
import click
from pathlib import Path
import subprocess
import logging

logger = logging.getLogger(__name__)


@click.command()
def quickstart():
    """Lance un assistant de configuration rapide pour le projet Altiora."

    Cette commande est conçue pour les nouveaux utilisateurs afin de les aider
    à démarrer rapidement avec un environnement de travail fonctionnel.
    """
    click.echo("🚀 Altiora Quickstart – Suivez le guide pour une configuration rapide !\n")

    # 1. Vérifie si un projet Altiora est déjà présent. Si non, propose de cloner un exemple.
    if not Path("src").exists():
        if click.confirm("Aucun projet Altiora détecté dans le répertoire courant. Voulez-vous cloner un projet d'exemple ?"):
            url = "https://github.com/altiora/template.git" # URL du template de projet.
            try:
                # Clone le dépôt temporairement, déplace les fichiers, puis supprime le dépôt temporaire.
                subprocess.run(["git", "clone", url, ".altiora_temp"], check=True, capture_output=True, text=True)
                # Utilise shutil.move pour déplacer les contenus de manière plus robuste.
                for item in Path(".altiora_temp").iterdir():
                    shutil.move(str(item), ".")
                Path(".altiora_temp").rmdir()
                click.echo("✅ Projet d'exemple cloné et configuré.")
            except subprocess.CalledProcessError as e:
                click.echo(f"❌ Erreur lors du clonage du projet : {e.stderr}")
                logger.error(f"Erreur lors du clonage du projet : {e.stderr}")
                return # Arrête le quickstart en cas d'échec.
            except Exception as e:
                click.echo(f"❌ Erreur inattendue lors de la configuration du projet : {e}")
                logger.error(f"Erreur inattendue lors de la configuration du projet : {e}")
                return
        else:
            click.echo("Opération annulée. Veuillez créer ou naviguer vers un projet Altiora existant.")
            return
    else:
        click.echo("✅ Projet Altiora déjà présent dans le répertoire courant.")

    # 2. Configuration des variables d'environnement dans le fichier `.env`.
    env_path = Path(".env")
    if not env_path.exists():
        click.echo("📝 Création du fichier `.env` pour les variables d'environnement.")
        # Demande à l'utilisateur de fournir des clés ou génère des valeurs par défaut.
        jwt_secret = click.prompt("JWT_SECRET_KEY (laisser vide pour générer automatiquement)", default="", show_default=False)
        encryption_key = click.prompt("ENCRYPTION_KEY (laisser vide pour générer automatiquement)", default="", show_default=False)
        
        # Génère des clés si l'utilisateur n'en fournit pas.
        if not jwt_secret: jwt_secret = os.urandom(32).hex()
        if not encryption_key: encryption_key = os.urandom(32).hex()

        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(f"JWT_SECRET_KEY={jwt_secret}\n")
                f.write(f"ENCRYPTION_KEY={encryption_key}\n")
                f.write("# Ajoutez d'autres variables d'environnement ici si nécessaire.\n")
            click.echo(f"✅ Fichier `.env` créé avec les clés générées.")
        except (IOError, OSError) as e:
            click.echo(f"❌ Erreur lors de la création du fichier .env : {e}")
            logger.error(f"Erreur lors de la création du fichier .env : {e}")
            return
    else:
        click.echo("✅ Fichier `.env` déjà présent.")

    # 3. Construction des images Docker du projet.
    click.echo("\n⚙️  Construction des images Docker du projet...")
    try:
        subprocess.run(["docker-compose", "build"], check=True, capture_output=True, text=True)
        click.echo("✅ Images Docker construites avec succès.")
    except FileNotFoundError:
        click.echo("❌ Erreur: `docker-compose` n'est pas installé ou n'est pas dans le PATH.")
        logger.error("docker-compose non trouvé.")
        return
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Erreur lors de la construction des images Docker : {e.stderr}")
        logger.error(f"Erreur lors de la construction des images Docker : {e.stderr}")
        return

    # 4. Lancement des services Docker.
    click.echo("\n🎉 Lancement des services Altiora...")
    try:
        subprocess.run(["docker-compose", "up", "-d"], check=True, capture_output=True, text=True)
        click.echo("✅ Services Altiora démarrés avec succès en arrière-plan.")
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Erreur lors du démarrage des services : {e.stderr}")
        logger.error(f"Erreur lors du démarrage des services : {e.stderr}")
        return

    click.echo("\n✅ Quickstart terminé ! Votre environnement Altiora est prêt.")
    click.echo("Vous pouvez maintenant accéder au tableau de bord via votre navigateur à http://localhost:8000 (ou le port configuré).")


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Pour tester ce script, vous pouvez simuler un environnement vide ou existant.
    # Assurez-vous que `docker-compose.yml` et `requirements.txt` existent dans le répertoire courant.

    print("\n--- Lancement de la démonstration du Altiora Quickstart ---")
    try:
        # Simule l'appel de la commande CLI.
        # sys.argv = ["cli/commands/quickstart.py"]
        # quickstart() # Appel direct de la fonction pour la démo.
        # Ou via subprocess pour simuler l'appel CLI complet.
        subprocess.run([sys.executable, __file__], check=True)

    except Exception as e:
        print(f"Une erreur est survenue lors de la démonstration : {e}")
    finally:
        # Nettoyage des fichiers temporaires créés par la démo (si nécessaire).
        # Par exemple, si un projet d'exemple a été cloné.
        # if Path(".altiora_temp").exists():
        #     import shutil
        #     shutil.rmtree(".altiora_temp")
        # if Path(".env").exists():
        #     Path(".env").unlink()
        print("Démonstration du quickstart terminée.")
