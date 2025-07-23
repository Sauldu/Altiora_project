# cli/commands/start.py
import click
import subprocess

@click.command()
def start():
    """Lance les services Altiora"""
    try:
        subprocess.run(["docker-compose", "up", "-d"], check=True)
        click.echo("Services Altiora démarrés avec succès.")
    except subprocess.CalledProcessError as e:
        click.echo(f"Erreur lors du démarrage des services: {e}")