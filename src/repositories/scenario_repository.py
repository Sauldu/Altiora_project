from pathlib import Path
from typing import Optional, List
import json
import logging

from src.repositories.base_repository import BaseRepository
from src.models.test_scenario import TestScenario

logger = logging.getLogger(__name__)


class ScenarioRepository(BaseRepository[TestScenario]):
    """Dépôt pour la persistance des objets `TestScenario` sur le système de fichiers.

    Chaque scénario est stocké comme un fichier JSON individuel dans un répertoire spécifié.
    """

    def __init__(self, storage_path: Path):
        """Initialise le dépôt de scénarios."

        Args:
            storage_path: Le chemin du répertoire où les fichiers JSON des scénarios seront stockés.
        """
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True) # Crée le répertoire si nécessaire.

    async def create(self, scenario: TestScenario) -> TestScenario:
        """Crée un nouveau fichier JSON pour un scénario de test."

        Args:
            scenario: L'objet `TestScenario` à persister.

        Returns:
            L'objet `TestScenario` qui a été persisté.

        Raises:
            ValueError: Si un scénario avec le même ID existe déjà.
            IOError: En cas d'erreur lors de l'écriture du fichier.
        """
        file_path = self.storage_path / f"{scenario.id}.json"
        if file_path.exists():
            raise ValueError(f"Un scénario avec l'ID {scenario.id} existe déjà.")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(scenario.model_dump(), f, ensure_ascii=False, indent=4)
            logger.info(f"Scénario créé : {file_path}")
            return scenario
        except (IOError, OSError) as e:
            logger.error(f"Erreur lors de la création du fichier de scénario {file_path}: {e}")
            raise IOError(f"Erreur lors de la création du fichier de scénario {file_path}: {e}") from e

    async def get(self, id: str) -> Optional[TestScenario]:
        """Récupère un scénario de test par son ID."

        Args:
            id: L'ID du scénario à récupérer.

        Returns:
            L'objet `TestScenario` si trouvé, sinon None.

        Raises:
            IOError: En cas d'erreur lors de la lecture ou du parsing du fichier.
        """
        file_path = self.storage_path / f"{id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Scénario récupéré : {file_path}")
            return TestScenario(**data)
        except (IOError, OSError, json.JSONDecodeError) as e:
            logger.error(f"Erreur lors de la lecture du fichier de scénario {file_path}: {e}")
            raise IOError(f"Erreur lors de la lecture du fichier de scénario {file_path}: {e}") from e

    async def update(self, id: str, scenario: TestScenario) -> TestScenario:
        """Met à jour un scénario de test existant."

        Args:
            id: L'ID du scénario à mettre à jour.
            scenario: L'objet `TestScenario` avec les données mises à jour.

        Returns:
            L'objet `TestScenario` mis à jour.

        Raises:
            FileNotFoundError: Si le scénario avec l'ID spécifié n'existe pas.
            IOError: En cas d'erreur lors de l'écriture du fichier.
        """
        file_path = self.storage_path / f"{id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Scénario avec l'ID {id} non trouvé.")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(scenario.model_dump(), f, ensure_ascii=False, indent=4)
            logger.info(f"Scénario mis à jour : {file_path}")
            return scenario
        except (IOError, OSError) as e:
            logger.error(f"Erreur lors de la mise à jour du fichier de scénario {file_path}: {e}")
            raise IOError(f"Erreur lors de la mise à jour du fichier de scénario {file_path}: {e}") from e

    async def delete(self, id: str) -> bool:
        """Supprime un scénario de test par son ID."

        Args:
            id: L'ID du scénario à supprimer.

        Returns:
            True si le scénario a été supprimé, False sinon.
        """
        file_path = self.storage_path / f"{id}.json"
        if file_path.exists():
            try:
                file_path.unlink() # Supprime le fichier.
                logger.info(f"Scénario supprimé : {file_path}")
                return True
            except (IOError, OSError) as e:
                logger.error(f"Erreur lors de la suppression du fichier de scénario {file_path}: {e}")
                return False
        return False

    async def get_all(self) -> List[TestScenario]:
        """Récupère tous les scénarios de test stockés."

        Returns:
            Une liste de tous les objets `TestScenario` trouvés.
        """
        scenarios = []
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                scenarios.append(TestScenario(**data))
            except (IOError, OSError, json.JSONDecodeError) as e:
                logger.warning(f"Erreur lors de la lecture ou du parsing du fichier de scénario {file_path}: {e}")
        logger.info(f"Récupéré {len(scenarios)} scénarios.")
        return scenarios


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging
    import uuid

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def demo():
        temp_storage_path = Path("temp_scenario_storage")
        # Nettoyage du répertoire de démonstration.
        if temp_storage_path.exists():
            import shutil
            shutil.rmtree(temp_storage_path)
        temp_storage_path.mkdir()

        repo = ScenarioRepository(temp_storage_path)

        print("\n--- Création de scénarios ---")
        scenario1_id = "SCN-001"
        scenario1 = TestScenario(
            id=scenario1_id,
            title="Connexion réussie",
            objective="Vérifier la connexion avec des identifiants valides.",
            steps=["Entrer email", "Entrer mot de passe", "Cliquer sur login"],
            expected_result="Redirection vers le tableau de bord."
        )
        created_scenario1 = await repo.create(scenario1)
        print(f"Créé : {created_scenario1.id}")

        scenario2_id = "SCN-002"
        scenario2 = TestScenario(
            id=scenario2_id,
            title="Mot de passe oublié",
            objective="Vérifier le processus de récupération de mot de passe.",
            steps=["Cliquer sur mot de passe oublié", "Entrer email", "Soumettre"],
            expected_result="Email de réinitialisation envoyé."
        )
        created_scenario2 = await repo.create(scenario2)
        print(f"Créé : {created_scenario2.id}")

        print("\n--- Récupération d'un scénario ---")
        retrieved_scenario = await repo.get(scenario1_id)
        if retrieved_scenario:
            print(f"Récupéré : {retrieved_scenario.title}")
        else:
            print(f"Scénario {scenario1_id} non trouvé.")

        print("\n--- Mise à jour d'un scénario ---")
        scenario1.objective = "Vérifier la connexion et la déconnexion."
        updated_scenario = await repo.update(scenario1_id, scenario1)
        print(f"Mis à jour : {updated_scenario.objective}")

        print("\n--- Récupération de tous les scénarios ---")
        all_scenarios = await repo.get_all()
        print(f"Tous les scénarios ({len(all_scenarios)}) : {[s.id for s in all_scenarios]}")

        print("\n--- Suppression d'un scénario ---")
        deleted = await repo.delete(scenario2_id)
        print(f"Scénario {scenario2_id} supprimé : {deleted}")

        all_scenarios_after_delete = await repo.get_all()
        print(f"Scénarios restants ({len(all_scenarios_after_delete)}) : {[s.id for s in all_scenarios_after_delete]}")

        print("Démonstration terminée. Nettoyage du répertoire temporaire.")
        import shutil
        shutil.rmtree(temp_storage_path)

    asyncio.run(demo())