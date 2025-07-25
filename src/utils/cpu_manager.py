# src/utils/cpu_manager.py
"""Module pour la gestion de l'affectation des ressources CPU.

Ce module fournit des outils pour optimiser l'utilisation des cœurs CPU,
particulièrement sur les architectures hybrides (P-cores et E-cores) comme
celles d'Intel (12ème génération et plus). Il permet de définir l'affinité
CPU d'un processus pour diriger les tâches vers les types de cœurs appropriés.
"""

import os
import psutil
import logging

logger = logging.getLogger(__name__)


class CPUResourceManager:
    """Gère l'affectation des ressources CPU pour optimiser les performances des modèles."

    Conçu pour les architectures CPU hybrides (P-cores et E-cores) comme Intel 12ème génération et plus.
    """

    def __init__(self):
        """Initialise le gestionnaire de ressources CPU."

        Les listes `p_cores` et `e_cores` sont des exemples basés sur un CPU Intel i5-13500H.
        Pour d'autres architectures, ces listes devraient être adaptées.
        """
        # Ces valeurs sont des exemples pour un i5-13500H.
        # Une détection plus robuste pourrait être nécessaire pour d'autres CPU.
        self.p_cores = list(range(0, 12, 2))  # Ex: cœurs logiques 0, 2, 4, 6, 8, 10 (P-cores)
        self.e_cores = list(range(1, 20, 2))  # Ex: cœurs logiques 1, 3, 5, ..., 19 (E-cores)
        logger.info(f"CPUResourceManager initialisé. P-cores: {self.p_cores}, E-cores: {self.e_cores}")

    def set_affinity_for_model(self, model_type: str):
        """Définit l'affinité CPU du processus courant en fonction du type de modèle."

        Cela permet de diriger les tâches gourmandes en performance vers les P-cores
        et les tâches plus légères ou de fond vers les E-cores.

        Args:
            model_type: Le type de modèle ('qwen3' pour les tâches lourdes, 'starcoder2' pour les tâches plus légères).
        """
        process = psutil.Process(os.getpid())
        
        try:
            if model_type == "qwen3":
                # Qwen3 est gourmand en calcul, on le dirige vers les P-cores.
                process.cpu_affinity(self.p_cores)
                logger.info(f"Affinité CPU définie pour Qwen3 (P-cores): {self.p_cores}")
            elif model_type == "starcoder2":
                # StarCoder2 peut être plus léger, on le dirige vers les E-cores.
                process.cpu_affinity(self.e_cores)
                logger.info(f"Affinité CPU définie pour StarCoder2 (E-cores): {self.e_cores}")
            else:
                logger.warning(f"Type de modèle inconnu '{model_type}'. Aucune affinité CPU définie.")
        except Exception as e:
            logger.error(f"Erreur lors de la définition de l'affinité CPU: {e}")


# ------------------------------------------------------------------
# Exemple d'utilisation (pour démonstration)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    manager = CPUResourceManager()

    print("\n--- Test de l'affinité CPU pour Qwen3 (simulé) ---")
    manager.set_affinity_for_model("qwen3")
    # Ici, le processus Python serait lié aux P-cores.
    # Pour vérifier sur un système Linux, vous pouvez utiliser `taskset -p <pid>`.
    # Sur Windows, l'affinité peut être vérifiée via le Gestionnaire des tâches.

    print("\n--- Test de l'affinité CPU pour StarCoder2 (simulé) ---")
    manager.set_affinity_for_model("starcoder2")
    # Ici, le processus Python serait lié aux E-cores.

    print("\n--- Test avec un type de modèle inconnu ---")
    manager.set_affinity_for_model("unknown_model")

    print("Démonstration du CPUResourceManager terminée.")