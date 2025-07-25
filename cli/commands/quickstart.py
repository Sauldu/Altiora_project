# cli/commands/quickstart.py
import os
import click
from pathlib import Path
import subprocess

@click.command()
def quickstart():
    """Assistant de configuration rapide."""
    click.echo("🚀 Altiora Quickstart – suivez le guide !\n")

    # Clone ou vérifie
    if not Path("src").exists():
        if click.confirm("Aucun projet détecté. Cloner l’exemple ?"):
            url = "https://github.com/altiora/template.git"
            subprocess.run(["git", "clone", url, ".altiora"], check=True)
            subprocess.run(["mv", ".altiora/*", "."], shell=True)
            subprocess.run(["rm", "-rf", ".altiora"], shell=True)
    else:
        click.echo("✅ Projet déjà présent.")

    # Variables d’env
    env_path = Path(".env")
    if not env_path.exists():
        click.echo("📝 Création du fichier .env")
        jwt = click.prompt("JWT_SECRET_KEY (laisser vide pour auto)", default="", show_default=False)
        enc  = click.prompt("ENCRYPTION_KEY (laisser vide pour auto)", default="", show_default=False)
        with open(env_path, "w") as f:
            f.write(f"JWT_SECRET_KEY={jwt or os.urandom(32).hex()}\n")
            f.write(f"ENCRYPTION_KEY={enc or os.urandom(32).hex()}\n")
    else:
        click.echo("✅ .env déjà présent.")

    # Build
    click.echo("\n⚙️  Construction des images Docker…")
    subprocess.run(["docker-compose", "build"], check=True)

    # Start
    click.echo("\n🎉 Lancement des services…")
    subprocess.run(["docker-compose", "up", "-d"], check=True)
    click.echo("\n✅ Quickstart terminé ! Visitez http://localhost:8000")