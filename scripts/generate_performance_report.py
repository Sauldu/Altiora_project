#!/usr/bin/env python3
"""
generate_performance_report.py
Generate an HTML + PNG performance dashboard for Altiora
"""

import gc
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
import psutil
from matplotlib import pyplot as plt

# Non-interactive backend (lighter, no GUI needed)
matplotlib.use("Agg")

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------
DEFAULT_OUTPUT_DIR = Path("reports/performance")
FIG_SIZE = (12, 8)
DPI = 300


# ------------------------------------------------------------------
# Report Generator
# ------------------------------------------------------------------
class PerformanceReportGenerator:
    """Generate CPU, memory, response-time and throughput charts + HTML report."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_report(self, metrics: Dict[str, Any]) -> Path:
        """Generate JSON + PNG + HTML report and return the HTML path."""
        report_data = self._build_report_data(metrics)
        self._dump_json(report_data)
        self._create_performance_charts(metrics)
        html_path = self._create_html_report(report_data)
        gc.collect()
        return html_path

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------
    def _build_report_data(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Structure the final payload."""
        return {
            "timestamp": datetime.now().isoformat(),
            "system_info": {
                "cpu_cores": psutil.cpu_count(logical=False),
                "cpu_threads": psutil.cpu_count(logical=True),
                "memory_gb": psutil.virtual_memory().total / (1024 ** 3),
                "python_version": sys.version,
            },
            "metrics": metrics,
            "recommendations": self._generate_recommendations(metrics),
        }

    def _dump_json(self, data: Dict[str, Any]) -> None:
        """Save raw JSON for further processing."""
        try:
            with (self.output_dir / "performance_metrics.json").open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except (IOError, OSError) as e:
            logger.error(f"Error writing performance metrics JSON: {e}")

    def _create_performance_charts(self, metrics: Dict[str, Any]) -> None:
        """Draw 4 sub-plots and save PNG."""
        cpu: List[float] = metrics.get("cpu_usage", [])
        mem: List[float] = metrics.get("memory_usage", [])
        rt: List[float] = metrics.get("response_times", [])
        tp: float = metrics.get("throughput", 0.0)

        fig, axes = plt.subplots(2, 2, figsize=FIG_SIZE)

        # CPU
        axes[0, 0].plot(cpu or [0])
        axes[0, 0].set_title("Utilisation CPU")
        axes[0, 0].set_ylabel("%")

        # Memory
        axes[0, 1].plot(mem or [0])
        axes[0, 1].set_title("Utilisation Mémoire")
        axes[0, 1].set_ylabel("GB")

        # Response time histogram
        axes[1, 0].hist(rt or [0], bins=min(len(rt) or 1, 20), color="skyblue", edgecolor="black")
        axes[1, 0].set_title("Distribution des temps de réponse")
        axes[1, 0].set_xlabel("Secondes")

        # Throughput bar
        axes[1, 1].bar(["Throughput"], [tp])
        axes[1, 1].set_title("Débit")
        axes[1, 1].set_ylabel("Req/s")

        plt.tight_layout()
        fig.savefig(self.output_dir / "performance_charts.png", dpi=DPI)
        plt.close(fig)  # release memory

    @staticmethod
    def _generate_recommendations(metrics: Dict[str, Any]) -> List[str]:
        """Return simple textual recommendations."""
        recs = []
        if metrics.get("success_rate", 100) < 90:
            recs.append("Augmentez la robustesse des tests ou la capacité CPU.")
        if metrics.get("avg_duration", 0) > 60:
            recs.append("Réduisez le temps moyen de réponse (optimisation ou cache).")
        if metrics.get("memory_usage", [0])[-1] > 20:
            recs.append("Surveillez la mémoire : envisagez un GC plus fréquent ou des limites Docker.")
        return recs or ["Tout semble dans les clous !"]

    def _create_html_report(self, data: Dict[str, Any]) -> Path:
        """Generate self-contained HTML report."""
        html = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>Rapport de Performance – Altiora</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .metric {{ background: #f7f7f7; padding: 12px; margin: 8px 0; border-radius: 6px; }}
        .success {{ color: #2e7d32; }} .warning {{ color: #ff8f00; }} .error {{ color: #c62828; }}
        img {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    <h1>Rapport de Performance – Altiora</h1>
    <p><strong>Généré le :</strong> {data['timestamp']}</p>

    <h2>Vue d’ensemble</h2>
    <div class="metric">
        <strong>Succès :</strong> {data['metrics'].get('success_rate', 0):.1f}%
    </div>
    <div class="metric">
        <strong>Débit moyen :</strong> {data['metrics'].get('throughput', 0):.2f} req/s
    </div>
    <div class="metric">
        <strong>Temps moyen :</strong> {data['metrics'].get('avg_duration', 0):.2f} s
    </div>

    <h2>Recommandations</h2>
    <ul>
        {''.join(f"<li>{r}</li>" for r in data['recommendations'])}
    </ul>

    <img src="performance_charts.png" alt="Graphiques de performance">
</body>
</html>
        """
        html_path = self.output_dir / "performance_report.html"
        try:
            html_path.write_text(html, encoding="utf-8")
        except (IOError, OSError) as e:
            logger.error(f"Error writing HTML report: {e}")
        return html_path


# ------------------------------------------------------------------
# CLI / Demo
# ------------------------------------------------------------------
if __name__ == "__main__":
    generator = PerformanceReportGenerator()

    sample: Dict[str, Any] = {
        "success_rate": 95.5,
        "throughput": 2.3,
        "avg_duration": 45.2,
        "cpu_usage": [45, 67, 78, 82, 75],
        "memory_usage": [8.5, 12.3, 15.7, 18.2, 16.8],
        "response_times": [30, 35, 42, 38, 45, 52, 48],
    }

    print("📊 Génération du rapport de performance…")
    report_file = generator.generate_report(sample)
    print(f"✅ Rapport sauvegardé : {report_file}")
