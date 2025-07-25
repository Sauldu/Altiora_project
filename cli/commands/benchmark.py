# cli/commands/benchmark.py
"""Commande `benchmark` pour la CLI Altiora.

Ce module fournit une commande pour lancer les tests de performance
du projet. Il utilise `pytest-benchmark` pour exécuter des benchmarks
et générer un rapport détaillé.
"""

import click
import subprocess
import logging

logger = logging.getLogger(__name__)


@click.command()
@click.option("--runs", default=5, help="Nombre de runs par benchmark pour chaque test de performance.")
def benchmark(runs: int):
    """Lance les tests de performance de l'application Altiora."

    Cette commande exécute les tests situés dans le répertoire `tests/performance`
    en utilisant `pytest-benchmark`. Un rapport JSON est généré à la fin de l'exécution.

    Args:
        runs: Le nombre de fois que chaque test de performance sera exécuté.
    """
    click.echo("📊 Altiora Benchmark – Démarrage des tests de performance...")
    cmd = [
        "pytest",
        "tests/performance", # Cible le répertoire des tests de performance.
        "--benchmark-only", # Exécute uniquement les tests marqués comme benchmarks.
        f"--benchmark-warmup-iterations={runs}", # Nombre d'itérations de chauffe.
        f"--benchmark-json=benchmark-report.json", # Fichier de sortie du rapport JSON.
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        click.echo("✅ Benchmark terminé. Rapport généré dans `benchmark-report.json`.")
        logger.info("Benchmark terminé avec succès.")
    except FileNotFoundError:
        click.echo("❌ Erreur: `pytest` ou `pytest-benchmark` n'est pas installé. Assurez-vous d'avoir installé les dépendances de développement.")
        logger.error("pytest ou pytest-benchmark non trouvé.")
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Erreur lors de l'exécution des benchmarks : {e.stderr}")
        logger.error(f"Erreur lors de l'exécution des benchmarks : {e.stderr}")
    except Exception as e:
        click.echo(f"❌ Une erreur inattendue est survenue : {e}")
        logger.error(f"Erreur inattendue lors de l'exécution des benchmarks : {e}")


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import os

    # Pour la démonstration, nous allons simuler un fichier de test de performance.
    # En temps normal, ces fichiers existeraient déjà dans `tests/performance`.
    temp_test_dir = Path("tests/performance")
    temp_test_dir.mkdir(parents=True, exist_ok=True)
    (temp_test_dir / "test_example_benchmark.py").write_text("""
import pytest
import time

@pytest.mark.benchmark(group="example")
def test_simple_operation():
    time.sleep(0.01) # Simule une opération rapide.

@pytest.mark.benchmark(group="example")
def test_complex_operation():
    time.sleep(0.1) # Simule une opération plus lente.
""")

    # Exécute la commande benchmark via le système.
    # Note: Cela nécessite que `pytest` et `pytest-benchmark` soient installés dans l'environnement.
    print("\n--- Lancement de la démonstration du benchmark ---")
    try:
        # Simule l'appel de la commande CLI.
        # sys.argv = ["cli/commands/benchmark.py", "--runs", "2"]
        # benchmark() # Appel direct de la fonction pour la démo.
        # Ou via subprocess pour simuler l'appel CLI complet.
        subprocess.run([sys.executable, __file__, "--runs", "2"], check=True)

    except Exception as e:
        print(f"Une erreur est survenue lors de la démonstration : {e}")
    finally:
        # Nettoyage des fichiers temporaires.
        if temp_test_dir.exists():
            import shutil
            shutil.rmtree(temp_test_dir)
        if Path("benchmark-report.json").exists():
            Path("benchmark-report.json").unlink()
        print("Démonstration du benchmark terminée.")