# cli/commands/test.py
import click
import subprocess

@click.command()
def test():
    """Exécute les tests Altiora"""
    try:
        subprocess.run(["pytest"], check=True)
        click.echo("Tests Altiora exécutés avec succès.")
    except subprocess.CalledProcessError as e:
        click.echo(f"Erreur lors de l'exécution des tests: {e}")