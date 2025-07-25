from pathlib import Path
from typing import Optional, List
import json

from src.repositories.base_repository import BaseRepository
from src.models.test_scenario import TestScenario

class ScenarioRepository(BaseRepository[TestScenario]):
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def create(self, scenario: TestScenario) -> TestScenario:
        file_path = self.storage_path / f"{scenario.id}.json"
        if file_path.exists():
            raise ValueError(f"Scenario with ID {scenario.id} already exists.")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(scenario.model_dump(), f, ensure_ascii=False, indent=4)
            return scenario
        except (IOError, OSError) as e:
            raise IOError(f"Error creating scenario file {file_path}: {e}") from e

    async def get(self, id: str) -> Optional[TestScenario]:
        file_path = self.storage_path / f"{id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return TestScenario(**data)
        except (IOError, OSError, json.JSONDecodeError) as e:
            raise IOError(f"Error reading scenario file {file_path}: {e}") from e

    async def update(self, id: str, scenario: TestScenario) -> TestScenario:
        file_path = self.storage_path / f"{id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Scenario with ID {id} not found.")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(scenario.model_dump(), f, ensure_ascii=False, indent=4)
            return scenario
        except (IOError, OSError) as e:
            raise IOError(f"Error updating scenario file {file_path}: {e}") from e

    async def delete(self, id: str) -> bool:
        file_path = self.storage_path / f"{id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    async def get_all(self) -> List[TestScenario]:
        scenarios = []
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                scenarios.append(TestScenario(**data))
            except (IOError, OSError, json.JSONDecodeError) as e:
                logger.info(f"Error reading scenario file {file_path}: {e}")
        return scenarios