# cli/commands/test.py
"""Commande `test` pour la CLI Altiora."""

import click
import subprocess

@click.command()
def test():
    """Exécute la suite de tests du projet avec pytest."""
    try:
        # Exécute pytest pour lancer tous les tests découvrables.
        subprocess.run(["pytest"], check=True)
        click.echo("✅ Tests exécutés avec succès.")
    except FileNotFoundError:
        click.echo("❌ Erreur: `pytest` n'est pas installé. Exécutez `pip install pytest`.")
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Des tests ont échoué : {e}")
