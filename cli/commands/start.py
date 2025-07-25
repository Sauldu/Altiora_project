# cli/commands/start.py
"""Commande `start` pour la CLI Altiora."""

import click
import subprocess

@click.command()
def start():
    """Lance tous les services Altiora en utilisant docker-compose."""
    try:
        # Exécute `docker-compose up -d` pour démarrer les services en arrière-plan.
        subprocess.run(["docker-compose", "up", "-d"], check=True)
        click.echo("✅ Services Altiora démarrés avec succès.")
    except FileNotFoundError:
        click.echo("❌ Erreur: `docker-compose` n'est pas installé ou n'est pas dans le PATH.")
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Erreur lors du démarrage des services : {e}")
