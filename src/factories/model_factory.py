from enum import Enum
from typing import Union
import logging

from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from src.models.starcoder2.starcoder2_interface import StarCoder2OllamaInterface

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Énumération des types de modèles d'IA supportés par la fabrique."""
    QWEN3 = "qwen3"
    STARCODER2 = "starcoder2"


class ModelFactory:
    """Fabrique pour la création et la gestion des instances de modèles d'IA.

    Cette fabrique implémente le pattern Singleton pour chaque type de modèle,
    assurant qu'une seule instance d'un modèle donné est créée et réutilisée
    tout au long de l'application. Cela permet d'optimiser l'utilisation des
    ressources en évitant de charger plusieurs fois le même modèle en mémoire.
    """
    _instances: Dict[ModelType, Union[Qwen3OllamaInterface, StarCoder2OllamaInterface]] = {}
    
    @classmethod
    async def create(cls, model_type: ModelType) -> Union[Qwen3OllamaInterface, StarCoder2OllamaInterface]:
        """Crée ou récupère une instance de modèle d'IA."

        Si une instance du modèle demandé existe déjà, elle est retournée.
        Sinon, une nouvelle instance est créée, initialisée et stockée.

        Args:
            model_type: Le type de modèle à créer ou à récupérer (ex: `ModelType.QWEN3`).

        Returns:
            Une instance du modèle d'IA spécifié.

        Raises:
            ValueError: Si le type de modèle demandé n'est pas reconnu.
        """
        if model_type not in cls._instances:
            logger.info(f"Création d'une nouvelle instance pour le modèle : {model_type.value}")
            if model_type == ModelType.QWEN3:
                instance = Qwen3OllamaInterface()
            elif model_type == ModelType.STARCODER2:
                instance = StarCoder2OllamaInterface()
            else:
                raise ValueError(f"Type de modèle inconnu : {model_type}")
            
            await instance.initialize()
            cls._instances[model_type] = instance
        else:
            logger.info(f"Réutilisation de l'instance existante pour le modèle : {model_type.value}")
        
        return cls._instances[model_type]


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def demo():
        print("\n--- Démonstration de ModelFactory ---")

        # Création/récupération d'une instance de Qwen3.
        print("Création de Qwen3...")
        qwen3_instance_1 = await ModelFactory.create(ModelType.QWEN3)
        print(f"Instance Qwen3 1 : {qwen3_instance_1}")

        print("Création de Qwen3 (devrait réutiliser l'instance existante)...")
        qwen3_instance_2 = await ModelFactory.create(ModelType.QWEN3)
        print(f"Instance Qwen3 2 : {qwen3_instance_2}")
        assert qwen3_instance_1 is qwen3_instance_2, "Les instances de Qwen3 devraient être les mêmes."

        # Création/récupération d'une instance de StarCoder2.
        print("\nCréation de StarCoder2...")
        starcoder2_instance_1 = await ModelFactory.create(ModelType.STARCODER2)
        print(f"Instance StarCoder2 1 : {starcoder2_instance_1}")

        print("Création de StarCoder2 (devrait réutiliser l'instance existante)...")
        starcoder2_instance_2 = await ModelFactory.create(ModelFactory.STARCODER2)
        print(f"Instance StarCoder2 2 : {starcoder2_instance_2}")
        assert starcoder2_instance_1 is starcoder2_instance_2, "Les instances de StarCoder2 devraient être les mêmes."

        # Nettoyage des instances (si les interfaces ont une méthode close).
        if hasattr(qwen3_instance_1, 'close'):
            await qwen3_instance_1.close()
        if hasattr(starcoder2_instance_1, 'close'):
            await starcoder2_instance_1.close()

        print("Démonstration de ModelFactory terminée.")

    asyncio.run(demo())