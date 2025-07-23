from enum import Enum
from typing import Union

from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from src.models.starcoder2.starcoder2_interface import StarCoder2OllamaInterface

class ModelType(Enum):
    QWEN3 = "qwen3"
    STARCODER2 = "starcoder2"

class ModelFactory:
    _instances = {}
    
    @classmethod
    async def create(cls, model_type: ModelType) -> Union[Qwen3OllamaInterface, StarCoder2OllamaInterface]:
        if model_type not in cls._instances:
            if model_type == ModelType.QWEN3:
                instance = Qwen3OllamaInterface()
            elif model_type == ModelType.STARCODER2:
                instance = StarCoder2OllamaInterface()
            else:
                raise ValueError(f"Unknown model type: {model_type}")
            
            await instance.initialize()
            cls._instances[model_type] = instance
        
        return cls._instances[model_type]