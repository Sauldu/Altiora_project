# cli/commands/benchmark.py
import click
import subprocess

@click.command()
@click.option("--runs", default=5, help="Nombre de runs par benchmark")
def benchmark(runs):
    """Lance les tests de performance."""
    click.echo("📊 Altiora Benchmark – démarrage…")
    cmd = [
        "pytest",
        "tests/performance",
        "--benchmark-only",
        f"--benchmark-warmup-iterations={runs}",
        "--benchmark-json=benchmark-report.json",
    ]
    subprocess.run(cmd, check=True)
    click.echo("✅ Benchmark terminé – voir benchmark-report.json")