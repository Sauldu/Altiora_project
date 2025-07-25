# cli/commands/doctor.py
import os
import subprocess
import sys
from pathlib import Path
import click
import pkg_resources

@click.command()
def doctor():
    """Diagnostic complet du projet Altiora."""
    ok = True
    click.echo("🔍 Altiora Doctor – Diagnostic…\n")

    # Python version
    v = sys.version_info
    if v < (3, 9):
        click.echo(f"❌ Python >= 3.9 requis (actuel {v.major}.{v.minor})")
        ok = False
    else:
        click.echo("✅ Python version")

    # Dépendances
    try:
        pkg_resources.require(open("requirements.txt").readlines())
        click.echo("✅ Dépendances installées")
    except Exception as e:
        click.echo(f"❌ Dépendances manquantes : {e}")
        ok = False

    # Docker
    if subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        click.echo("❌ Docker non disponible")
        ok = False
    else:
        click.echo("✅ Docker")

    # Fichiers obligatoires
    for f in ("src", "configs", "docker-compose.yml"):
        if not Path(f).exists():
            click.echo(f"❌ Fichier/dossier manquant : {f}")
            ok = False
    click.echo("✅ Arborescence")

    # Variables d’environnement critiques
    required = ("JWT_SECRET_KEY", "ENCRYPTION_KEY")
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        click.echo(f"❌ Variables manquantes : {', '.join(missing)}")
        ok = False
    else:
        click.echo("✅ Variables d’environnement")

    click.echo("\n" + ("✅ Tout semble OK !" if ok else "❌ Des erreurs ont été détectées."))