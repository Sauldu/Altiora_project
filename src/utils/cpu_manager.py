# src/utils/cpu_manager.py
import os
import psutil


class CPUResourceManager:
    def __init__(self):
        self.p_cores = list(range(0, 12, 2))  # P-cores pairs
        self.e_cores = list(range(1, 20, 2))  # E-cores impairs

    def set_affinity_for_model(self, model_type: str):
        """Assigne-les cores appropriés selon le modèle"""
        process = psutil.Process(os.getpid())

        if model_type == "qwen3":
            # Utiliser uniquement les P-cores pour Qwen3
            process.cpu_affinity(self.p_cores)
        else:
            # Utiliser les E-cores pour les tâches légères
            process.cpu_affinity(self.e_cores)


