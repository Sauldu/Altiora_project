# cli/main.py
"""Point d'entrée principal pour l'interface en ligne de commande (CLI) d'Altiora.

Ce module utilise la bibliothèque `click` pour créer une CLI robuste et facile à utiliser.
Il agrège toutes les commandes disponibles depuis le sous-package `cli.commands`.
"""

from pathlib import Path
import click
from cli.commands import init, start, test
from cli.commands import doctor, quickstart, benchmark

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Altiora CLI – Outil pour simplifier le développement et la gestion de projets Altiora."""
    # Si aucune sous-commande n'est invoquée, affiche l'aide.
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

# Enregistrement des commandes auprès du groupe principal.
cli.add_command(init.init)
cli.add_command(start.start)
cli.add_command(test.test)
cli.add_command(doctor.doctor)
cli.add_command(quickstart.quickstart)
cli.add_command(benchmark.benchmark)

def check_project_directory() -> bool:
    """Vérifie si le répertoire courant semble être un projet Altiora valide."""
    if not (Path("src").exists() and Path("configs").exists()):
        click.echo("❌ Ce répertoire ne ressemble pas à un projet Altiora.")
        return False
    return True

if __name__ == "__main__":
    cli()
