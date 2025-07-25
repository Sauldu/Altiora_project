# src/core/model_memory_manager.py
import gc
import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import Dict, Any

class ModelMemoryManager:
    """Gestionnaire de mémoire pour les modèles d'IA, avec déchargement LRU."""
    def __init__(self, max_memory_gb: float = 16.0):
        self.max_memory_gb = max_memory_gb
        self.loaded_models: Dict[str, Dict[str, Any]] = {}
        logger.info(f"Memory Manager initialized with a limit of {max_memory_gb} GB.")

    def can_load_model(self, model_name: str, size_gb: float) -> bool:
        """Check if model can be loaded without exceeding memory limits"""
        current_usage = sum(model_info['size'] for model_info in self.loaded_models.values())
        available = self.max_memory_gb - current_usage
        return size_gb <= available

    async def load_model_with_fallback(self, model_name: str, size_gb: float):
        """Load model with automatic fallback to quantized version"""
        if not self.can_load_model(model_name, size_gb):
            # Try to free memory
            await self._evict_least_used_model()

        if not self.can_load_model(model_name, size_gb):
            # Fallback to quantized version
            return await self._load_quantized_model(model_name)

        # Load the full model
        return await self._load_full_model(model_name)

    async def _evict_least_used_model(self):
        """Evict the least recently used model to free memory"""
        if not self.loaded_models:
            return

        # Find the least recently used model
        oldest_model_name = min(self.loaded_models, key=lambda k: self.loaded_models[k]['last_used'])
        logger.info(f"Memory limit reached. Unloading least recently used model: {oldest_model_name}")

        # Remove the model from the dictionary
        del self.loaded_models[oldest_model_name]

        # Explicitly clean up memory
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    async def _load_full_model(self, model_name: str):
        """Load the full model without quantization"""
        logger.info(f"Loading full model: {model_name}")
        try:
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                device_map="auto",
                torch_dtype=torch.float16
            )
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model_size = self._get_model_size(model)
            self.loaded_models[model_name] = {
                'model': model,
                'tokenizer': tokenizer,
                'last_used': time.time(),
                'size': model_size
            }
            logger.info(f"Model {model_name} loaded successfully.")
            return model
        except Exception as e:
            logger.info(f"Failed to load model {model_name}: {e}")
            raise

    async def _load_quantized_model(self, model_name: str):
        """Load the quantized model"""
        logger.info(f"Loading quantized model: {model_name}")
        try:
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                load_in_8bit=True,  # Quantization 8-bit
                device_map="auto",
                torch_dtype=torch.float16
            )
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model_size = self._get_model_size(model)
            self.loaded_models[model_name] = {
                'model': model,
                'tokenizer': tokenizer,
                'last_used': time.time(),
                'size': model_size
            }
            logger.info(f"Quantized model {model_name} loaded successfully.")
            return model
        except Exception as e:
            logger.info(f"Failed to load quantized model {model_name}: {e}")
            raise

    def _get_model_size(self, model) -> float:
        """Estimate the size in GB of a model"""
        param_size = 0
        for param in model.parameters():
            param_size += param.nelement() * param.element_size()
        buffer_size = 0
        for buffer in model.buffers():
            buffer_size += buffer.nelement() * buffer.element_size()
        return (param_size + buffer_size) / (1024 ** 3)  # Convert to GB

    async def get_model(self, model_name: str):
        """Retrieve a model, load it if necessary"""
        if model_name in self.loaded_models:
            self.loaded_models[model_name]['last_used'] = time.time()
            return self.loaded_models[model_name]['model']

        # Attempt to load full model first
        if self.can_load_model(model_name, 0): # Pass 0 as placeholder, actual size checked inside _load_full_model
            model = await self._load_full_model(model_name)
            return model
        else:
            # Fallback to quantized model
            model = await self._load_quantized_model(model_name)
            return model