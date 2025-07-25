#!/usr/bin/env python3
"""Génère un rapport de performance HTML et PNG à partir de métriques.

Ce script prend un dictionnaire de métriques de performance (utilisation CPU,
mémoire, temps de réponse, etc.) et génère un rapport visuel comprenant :
- Un fichier JSON brut avec toutes les données.
- une image PNG avec des graphiques (utilisation CPU/mémoire, histogramme des
  temps de réponse, etc.).
- Un fichier HTML auto-contenu qui affiche les métriques clés, les graphiques
  et des recommandations simples.

Ce script est conçu pour être appelé à la fin d'une suite de tests de performance.
"""

import gc
import json
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
import psutil
from matplotlib import pyplot as plt

# Utilise un backend non-interactif pour Matplotlib, car aucune GUI n'est nécessaire.
matplotlib.use("Agg")

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constantes
# ------------------------------------------------------------------
DEFAULT_OUTPUT_DIR = Path("reports/performance")
FIG_SIZE = (12, 8)
DPI = 300


# ------------------------------------------------------------------
# Générateur de Rapport
# ------------------------------------------------------------------
class PerformanceReportGenerator:
    """Génère des graphiques CPU, mémoire, temps de réponse et un rapport HTML."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        """Initialise le générateur de rapport."""
        self.output_dir = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # API Publique
    # ------------------------------------------------------------------
    def generate_report(self, metrics: Dict[str, Any]) -> Path:
        """Génère les fichiers JSON, PNG, et HTML du rapport et retourne le chemin du HTML."""
        report_data = self._build_report_data(metrics)
        self._dump_json(report_data)
        self._create_performance_charts(metrics)
        html_path = self._create_html_report(report_data)
        gc.collect()  # Force le garbage collection pour libérer la mémoire de Matplotlib.
        return html_path

    # ------------------------------------------------------------------
    # Assistants Privés
    # ------------------------------------------------------------------
    def _build_report_data(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Structure le payload final pour le rapport JSON et HTML."""
        return {
            "timestamp": datetime.now().isoformat(),
            "system_info": {
                "cpu_cores": psutil.cpu_count(logical=False),
                "cpu_threads": psutil.cpu_count(logical=True),
                "memory_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
                "python_version": sys.version,
            },
            "metrics": metrics,
            "recommendations": self._generate_recommendations(metrics),
        }

    def _dump_json(self, data: Dict[str, Any]) -> None:
        """Sauvegarde les données brutes au format JSON pour un traitement ultérieur."""
        try:
            json_path = self.output_dir / "performance_metrics.json"
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except (IOError, OSError) as e:
            logger.error(f"Erreur lors de l'écriture du JSON des métriques de performance : {e}")

    def _create_performance_charts(self, metrics: Dict[str, Any]) -> None:
        """Dessine 4 sous-graphiques et les sauvegarde dans une image PNG."""
        cpu: List[float] = metrics.get("cpu_usage", [])
        mem: List[float] = metrics.get("memory_usage_gb", [])
        rt: List[float] = metrics.get("response_times_s", [])
        tp: float = metrics.get("throughput_req_s", 0.0)

        fig, axes = plt.subplots(2, 2, figsize=FIG_SIZE)
        fig.suptitle('Tableau de Bord des Performances Altiora', fontsize=16)

        # Graphique CPU
        axes[0, 0].plot(cpu or [0], marker='o', linestyle='-', color='b')
        axes[0, 0].set_title("Utilisation CPU au fil du temps")
        axes[0, 0].set_ylabel("Utilisation (%)")
        axes[0, 0].grid(True)

        # Graphique Mémoire
        axes[0, 1].plot(mem or [0], marker='o', linestyle='-', color='r')
        axes[0, 1].set_title("Utilisation Mémoire au fil du temps")
        axes[0, 1].set_ylabel("Mémoire (GB)")
        axes[0, 1].grid(True)

        # Histogramme des temps de réponse
        axes[1, 0].hist(rt or [0], bins=min(len(rt) or 1, 20), color="skyblue", edgecolor="black")
        axes[1, 0].set_title("Distribution des Temps de Réponse")
        axes[1, 0].set_xlabel("Temps de réponse (s)")
        axes[1, 0].set_ylabel("Fréquence")

        # Barre de débit
        axes[1, 1].bar(["Débit"], [tp], color='g')
        axes[1, 1].set_title("Débit Moyen")
        axes[1, 1].set_ylabel("Requêtes/seconde")

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        try:
            fig.savefig(self.output_dir / "performance_charts.png", dpi=DPI)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des graphiques de performance : {e}")
        finally:
            plt.close(fig)  # Libère la mémoire utilisée par la figure.

    @staticmethod
    def _generate_recommendations(metrics: Dict[str, Any]) -> List[str]:
        """Retourne une liste de recommandations textuelles simples basées sur les métriques."""
        recs = []
        if metrics.get("success_rate", 100) < 95:
            recs.append("Le taux de succès est inférieur à 95%. Envisagez d'augmenter la robustesse des tests ou la capacité du système.")
        if metrics.get("avg_duration_s", 0) > 60:
            recs.append("Le temps de réponse moyen est supérieur à 60s. Pensez à optimiser le code ou à utiliser un cache plus agressif.")
        if metrics.get("memory_usage_gb", [0])[-1] > 20:
            recs.append("L'utilisation de la mémoire est élevée. Surveillez les fuites de mémoire ou envisagez d'augmenter les limites Docker.")
        return recs or ["Toutes les métriques semblent dans les clous. Bon travail !"]

    def _create_html_report(self, data: Dict[str, Any]) -> Path:
        """Génère un rapport HTML auto-contenu."""
        html_template = f"""... (le template HTML reste inchangé) ..."""
        html_path = self.output_dir / "performance_report.html"
        try:
            html_path.write_text(html_template, encoding="utf-8")
        except (IOError, OSError) as e:
            logger.error(f"Erreur lors de l'écriture du rapport HTML : {e}")
        return html_path


# ------------------------------------------------------------------
# CLI / Démonstration
# ------------------------------------------------------------------
if __name__ == "__main__":
    generator = PerformanceReportGenerator()

    # Exemple de données de métriques
    sample_metrics: Dict[str, Any] = {
        "success_rate": 95.5,
        "throughput_req_s": 2.3,
        "avg_duration_s": 45.2,
        "cpu_usage": [45, 67, 78, 82, 75, 70, 65],
        "memory_usage_gb": [8.5, 12.3, 15.7, 18.2, 16.8, 16.5, 16.0],
        "response_times_s": [30, 35, 42, 38, 45, 52, 48, 41, 46, 55],
    }

    logger.info("📊 Génération d'un exemple de rapport de performance...")
    report_file = generator.generate_report(sample_metrics)
    logger.info(f"✅ Rapport de performance sauvegardé ici : {report_file}")