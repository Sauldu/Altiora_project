# cli/main.py
from pathlib import Path
import click
from cli.commands import init, start, test
from cli.commands import doctor, quickstart, benchmark   # 👈 nouveaux modules

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Altiora CLI – expérience développeur simplifiée."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

# Commandes existantes
cli.add_command(init.init)
cli.add_command(start.start)
cli.add_command(test.test)

# Nouvelles commandes
cli.add_command(doctor.doctor)
cli.add_command(quickstart.quickstart)
cli.add_command(benchmark.benchmark)

def check_project_directory() -> bool:
    """Vérifie que l’on est dans un projet Altiora."""
    if not (Path("src").exists() and Path("configs").exists()):
        click.echo("❌ Ce répertoire ne ressemble pas à un projet Altiora.")
        return False
    return True

if __name__ == "__main__":
    cli()