import torch
from src.models.cpu_optimized_model import CPUOptimizedModel

# src/models/hybrid_engine.py
class HybridEngine:
    """Moteur hybride pour l'exécution de modèles, privilégiant le GPU et basculant sur le CPU si nécessaire.

    Cette classe est conçue pour optimiser l'utilisation des ressources matérielles
    en détectant la présence d'un GPU compatible CUDA. Si un GPU est disponible,
    il est utilisé pour l'inférence des modèles. Sinon, un modèle optimisé pour
    le CPU prend le relais.
    """
    def __init__(self):
        """Initialise le moteur hybride.

        Détecte automatiquement le meilleur appareil disponible (GPU ou CPU)
        et initialise le modèle de fallback CPU si nécessaire.
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.cpu_fallback = CPUOptimizedModel() # Instance du modèle optimisé pour le CPU.
        # Note: L'implémentation réelle de l'utilisation du modèle CPU ou GPU
        # devrait être gérée dans les méthodes d'inférence de cette classe.
