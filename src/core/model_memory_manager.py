import gc
import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

class ModelMemoryManager:
    """Gestionnaire de mémoire pour les modèles d'IA, avec déchargement LRU."""
    def __init__(self, max_memory_gb: float = 8.0):
        self.max_memory = max_memory_gb * 1024**3
        self.loaded_models = {}
        print(f"Memory Manager initialized with a limit of {max_memory_gb} GB.")

    def get_model(self, model_name: str):
        """Récupère un modèle, le charge si nécessaire."""
        if model_name in self.loaded_models:
            self.loaded_models[model_name]['last_used'] = time.time()
            return self.loaded_models[model_name]['model']
        
        # Libérer de la mémoire si nécessaire avant de charger
        self._ensure_memory_is_available()
        
        return self._load_model(model_name)

    def _load_model(self, model_name: str):
        """Charge un modèle avec des optimisations de mémoire."""
        print(f"Loading model: {model_name}")
        try:
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                load_in_8bit=True,  # Quantization 8-bit
                device_map="auto",
                torch_dtype=torch.float16
            )
            self.loaded_models[model_name] = {
                'model': model,
                'tokenizer': AutoTokenizer.from_pretrained(model_name),
                'last_used': time.time(),
                'size': self._get_model_size(model)
            }
            print(f"Model {model_name} loaded successfully.")
            return model
        except Exception as e:
            print(f"Failed to load model {model_name}: {e}")
            raise

    def _ensure_memory_is_available(self):
        """Vérifie la mémoire et décharge les modèles si nécessaire."""
        while self._get_used_memory() > self.max_memory * 0.8 and self.loaded_models:
            self._cleanup_oldest_model()

    def _cleanup_oldest_model(self):
        """Trouve et supprime le modèle le moins récemment utilisé."""
        if not self.loaded_models:
            return

        oldest_model_name = min(self.loaded_models, key=lambda k: self.loaded_models[k]['last_used'])
        print(f"Memory limit reached. Unloading least recently used model: {oldest_model_name}")
        
        del self.loaded_models[oldest_model_name]
        
        # Nettoyage explicite de la mémoire GPU/CPU
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _get_used_memory(self) -> int:
        """Calcule la mémoire totale utilisée par les modèles chargés."""
        return sum(model_info['size'] for model_info in self.loaded_models.values())

    def _get_model_size(self, model) -> int:
        """Estime la taille en octets d'un modèle."""
        param_size = 0
        for param in model.parameters():
            param_size += param.nelement() * param.element_size()
        buffer_size = 0
        for buffer in model.buffers():
            buffer_size += buffer.nelement() * buffer.element_size()
        return param_size + buffer_size
