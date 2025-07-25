"""Module pour gérer l'évolution de la personnalité de l'IA via le fine-tuning supervisé.

Ce module orchestre le processus d'entraînement LoRA en arrière-plan en utilisant
des exemples d'interactions de haute qualité.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Chemins basés sur la structure du projet
TRAINING_DATA_PATH = Path("data/training/data/train_dataset.jsonl")
TRAINING_SCRIPT_PATH = Path("data/training/src/train_qwen3_thinkpad.py")
ADAPTERS_OUTPUT_DIR = Path("data/models/lora_adapters")


class PersonalityEvolution:
    """
    Gère le cycle de vie du fine-tuning de la personnalité de l'IA.
    """

    def __init__(self):
        ADAPTERS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.training_process: Optional[asyncio.subprocess.Process] = None

    async def add_training_example(self, example: Dict[str, str]) -> bool:
        """
        Ajoute un nouvel exemple de haute qualité au dataset d'entraînement.

        L'exemple doit être un dictionnaire avec les clés "instruction", "input", "output".

        Args:
            example: Le dictionnaire contenant l'exemple d'entraînement.

        Returns:
            True si l'ajout a réussi, False sinon.
        """
        required_keys = {"instruction", "input", "output"}
        if not required_keys.issubset(example.keys()):
            logger.error(f"Exemple d'entraînement invalide. Clés requises: {required_keys}")
            return False

        try:
            with open(TRAINING_DATA_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(example, ensure_ascii=False) + "\n")
            logger.info(f"Nouvel exemple d'entraînement ajouté à {TRAINING_DATA_PATH}")
            return True
        except IOError as e:
            logger.error(f"Impossible d'écrire dans le fichier d'entraînement: {e}")
            return False

    async def trigger_finetuning_cycle(self, min_new_examples: int = 10) -> Dict[str, Any]:
        """
        Déclenche un nouveau cycle de fine-tuning si les conditions sont remplies.

        Args:
            min_new_examples: Nombre minimum de nouveaux exemples pour lancer un cycle.

        Returns:
            Un dictionnaire indiquant le statut du déclenchement.
        """
        if self.training_process and self.training_process.returncode is None:
            return {"status": "already_running", "pid": self.training_process.pid}

        if not TRAINING_SCRIPT_PATH.exists():
            logger.error(f"Script d'entraînement non trouvé: {TRAINING_SCRIPT_PATH}")
            return {"status": "error", "reason": "Training script not found"}

        # Note: Une logique plus avancée pourrait vérifier le nombre de nouvelles lignes
        # depuis le dernier entraînement.
        logger.info("Déclenchement d'un nouveau cycle de fine-tuning de la personnalité.")

        try:
            # Lancer le script d'entraînement en arrière-plan
            self.training_process = await asyncio.create_subprocess_exec(
                "python",
                str(TRAINING_SCRIPT_PATH),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            logger.info(f"Processus d'entraînement démarré avec le PID: {self.training_process.pid}")
            return {"status": "started", "pid": self.training_process.pid}
        except Exception as e:
            logger.error(f"Erreur lors du lancement du script d'entraînement: {e}")
            return {"status": "error", "reason": str(e)}

    async def get_training_status(self) -> Dict[str, Any]:
        """
        Vérifie le statut du processus d'entraînement en cours.
        """
        if not self.training_process:
            return {"status": "not_running"}

        if self.training_process.returncode is None:
            return {"status": "running", "pid": self.training_process.pid}
        else:
            stdout, stderr = await self.training_process.communicate()
            if self.training_process.returncode == 0:
                return {
                    "status": "completed_successfully",
                    "pid": self.training_process.pid,
                    "stdout": stdout.decode(),
                }
            else:
                return {
                    "status": "failed",
                    "pid": self.training_process.pid,
                    "returncode": self.training_process.returncode,
                    "stderr": stderr.decode(),
                }

    def get_latest_adapter(self) -> Optional[Path]:
        """
        Trouve le dernier adaptateur LoRA entraîné dans le répertoire de sortie.

        Returns:
            Le chemin vers le dernier adaptateur, ou None si aucun n'est trouvé.
        """
        try:
            adapters = [p for p in ADAPTERS_OUTPUT_DIR.iterdir() if p.is_dir() and p.name.startswith("checkpoint-")]
            if not adapters:
                return None
            # Trier par numéro de checkpoint pour trouver le plus récent
            latest_adapter = max(adapters, key=lambda p: int(p.name.split('-')[-1]))
            return latest_adapter
        except (FileNotFoundError, ValueError):
            return None


# --- Démonstration --- #
async def main():
    evolution = PersonalityEvolution()

    # 1. Ajouter un nouvel exemple
    new_example = {
        "instruction": "Reformule cette phrase de manière plus empathique.",
        "input": "Le ticket est fermé car le problème n'est pas reproductible.",
        "output": "Je comprends votre frustration. Pour l'instant, nous n'avons pas pu reproduire le problème pour le corriger, mais nous restons attentifs si de nouvelles informations apparaissent."
    }
    await evolution.add_training_example(new_example)

    # 2. Déclencher un cycle de fine-tuning (simulation)
    logger.info("\n--- Déclenchement du Fine-Tuning ---")
    # Pour la démo, nous allons simuler que le script existe.
    if not TRAINING_SCRIPT_PATH.exists():
        TRAINING_SCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        TRAINING_SCRIPT_PATH.write_text("print('Simulating a successful training run...')")
    
    start_result = await evolution.trigger_finetuning_cycle(min_new_examples=1)
    logger.info(f"Résultat du déclenchement: {start_result}")

    if start_result["status"] == "started":
        logger.info("Attente de la fin du processus d'entraînement (simulation)...")
        await asyncio.sleep(1)  # Simuler le temps d'entraînement
        status_result = await evolution.get_training_status()
        logger.info(f"Statut final: {status_result}")

    # 3. Trouver le dernier adaptateur (simulation)
    logger.info("\n--- Recherche du dernier adaptateur ---")
    # Simuler la création d'un adaptateur
    (ADAPTERS_OUTPUT_DIR / "checkpoint-100").mkdir(exist_ok=True)
    (ADAPTERS_OUTPUT_DIR / "checkpoint-200").mkdir(exist_ok=True)
    latest = evolution.get_latest_adapter()
    logger.info(f"Dernier adaptateur trouvé: {latest}")
    assert latest and latest.name == "checkpoint-200"


async def apply_personality_adapter(self, adapter_name: str):
    """Apply LoRA adapter for personality"""
    adapter_path = ADAPTERS_OUTPUT_DIR / f"{adapter_name}.bin"

    if not adapter_path.exists():
        logger.error(f"Adapter {adapter_name} not found")
        return False

    # Integration with Ollama
    command = [
        "ollama", "create",
        f"qwen3-{adapter_name}",
        "--adapter", str(adapter_path)
    ]

    result = await asyncio.create_subprocess_exec(*command)
    return result.returncode == 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())