# cli/commands/init.py
"""Commande `init` pour la CLI Altiora."""

import click
from pathlib import Path

@click.command()
@click.argument('project_name')
def init(project_name):
    """Initialise un nouveau projet Altiora avec une structure de base."""
    project_dir = Path(project_name)
    if project_dir.exists():
        click.echo(f"Le répertoire `{project_name}` existe déjà. L'initialisation est annulée.")
        return

    # Création de la structure de répertoires standard.
    project_dir.mkdir()
    (project_dir / "src").mkdir()
    (project_dir / "tests").mkdir()
    (project_dir / "configs").mkdir()
    (project_dir / "docs").mkdir()
    (project_dir / "scripts").mkdir()

    click.echo(f"✅ Projet `{project_name}` initialisé avec succès.")
