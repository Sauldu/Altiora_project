# src/optimization/memory_optimizer.py
import torch
import gc


class AdvancedMemoryOptimizer:
    def __init__(self):
        self.memory_pool = MemoryPool()

    def optimize_model_loading(self, model_path: str):
        """Charge le modèle avec optimisation mémoire maximale"""
        # Quantization 4-bit
        model = load_model_4bit(model_path)

        # Gradient checkpointing
        model.gradient_checkpointing_enable()

        # Memory mapping pour les poids
        model = self.memory_map_weights(model)

        # Garbage collection agressif
        gc.collect()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None

        return model