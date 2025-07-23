# cli/main.py
from pathlib import Path
import click
from cli.commands import init, start, test

@click.group()
def cli():
    """Altiora CLI - Gestion du projet Altiora"""
    pass

cli.add_command(init.init)
cli.add_command(start.start)
cli.add_command(test.test)


def check_project_directory() -> bool:
    """Ensure we are inside an Altiora project."""
    if not (Path("src").exists() and Path("configs").exists()):
        click.echo("❌  This directory does not look like an Altiora project.")
        return False
    return True

if __name__ == "__main__":
    cli()