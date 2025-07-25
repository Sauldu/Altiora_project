# src/modules/psychodesign/personality_evolution.py
"""Module pour gérer l'évolution de la personnalité de l'IA via le fine-tuning supervisé.

Ce module orchestre le processus d'entraînement LoRA en arrière-plan en utilisant
des exemples d'interactions de haute qualité. Il permet d'ajouter de nouveaux
exemples d'entraînement, de déclencher des cycles de fine-tuning, de vérifier
leur statut et de récupérer le chemin du dernier adaptateur entraîné.
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Chemins basés sur la structure du projet pour les données et scripts d'entraînement.
TRAINING_DATA_PATH = Path("data/training/data/train_dataset.jsonl")
TRAINING_SCRIPT_PATH = Path("data/training/src/train_qwen3_thinkpad.py")
ADAPTERS_OUTPUT_DIR = Path("data/models/lora_adapters")


class PersonalityEvolution:
    """Gère le cycle de vie du fine-tuning de la personnalité de l'IA."""

    def __init__(self):
        """Initialise le gestionnaire d'évolution de la personnalité."

        S'assure que le répertoire de sortie des adaptateurs existe.
        """
        ADAPTERS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.training_process: Optional[asyncio.subprocess.Process] = None

    async def add_training_example(self, example: Dict[str, str]) -> bool:
        """Ajoute un nouvel exemple de haute qualité au dataset d'entraînement."

        L'exemple doit être un dictionnaire avec les clés "instruction", "input", "output",
        conformément au format JSON Lines attendu par le script d'entraînement.

        Args:
            example: Le dictionnaire contenant l'exemple d'entraînement.

        Returns:
            True si l'ajout a réussi, False sinon.
        """
        required_keys = {"instruction", "input", "output"}
        if not required_keys.issubset(example.keys()):
            logger.error(f"Exemple d'entraînement invalide. Clés requises : {required_keys}. Clés fournies : {example.keys()}")
            return False

        try:
            # Crée le répertoire parent si nécessaire.
            TRAINING_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(TRAINING_DATA_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(example, ensure_ascii=False) + "\n")
            logger.info(f"Nouvel exemple d'entraînement ajouté à {TRAINING_DATA_PATH}.")
            return True
        except IOError as e:
            logger.error(f"Impossible d'écrire dans le fichier d'entraînement {TRAINING_DATA_PATH}: {e}")
            return False

    async def trigger_finetuning_cycle(self, min_new_examples: int = 10) -> Dict[str, Any]:
        """Déclenche un nouveau cycle de fine-tuning si les conditions sont remplies."

        Args:
            min_new_examples: Nombre minimum de nouveaux exemples requis pour lancer un cycle.
                              (La logique de vérification du nombre d'exemples n'est pas implémentée ici).

        Returns:
            Un dictionnaire indiquant le statut du déclenchement (started, already_running, error).
        """
        if self.training_process and self.training_process.returncode is None:
            logger.info(f"Un processus d'entraînement est déjà en cours (PID: {self.training_process.pid}).")
            return {"status": "already_running", "pid": self.training_process.pid}

        if not TRAINING_SCRIPT_PATH.exists():
            logger.error(f"Script d'entraînement non trouvé : {TRAINING_SCRIPT_PATH}.")
            return {"status": "error", "reason": "Training script not found"}

        logger.info("Déclenchement d'un nouveau cycle de fine-tuning de la personnalité...")

        try:
            # Lance le script d'entraînement en arrière-plan.
            # `asyncio.create_subprocess_exec` est utilisé pour exécuter un processus externe.
            self.training_process = await asyncio.create_subprocess_exec(
                "python",
                str(TRAINING_SCRIPT_PATH),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            logger.info(f"Processus d'entraînement démarré avec le PID : {self.training_process.pid}.")
            return {"status": "started", "pid": self.training_process.pid}
        except FileNotFoundError:
            logger.error("La commande 'python' ou le script d'entraînement n'a pas été trouvé. Assurez-vous que Python est dans le PATH et que le script existe.")
            return {"status": "error", "reason": "Python interpreter or training script not found"}
        except Exception as e:
            logger.error(f"Erreur lors du lancement du script d'entraînement : {e}")
            return {"status": "error", "reason": str(e)}

    async def get_training_status(self) -> Dict[str, Any]:
        """Vérifie le statut du processus d'entraînement en cours."

        Returns:
            Un dictionnaire décrivant le statut de l'entraînement (not_running, running, completed_successfully, failed).
        """
        if not self.training_process:
            return {"status": "not_running"}

        if self.training_process.returncode is None:
            return {"status": "running", "pid": self.training_process.pid}
        else:
            # Le processus est terminé, récupère la sortie standard et d'erreur.
            stdout, stderr = await self.training_process.communicate()
            if self.training_process.returncode == 0:
                return {
                    "status": "completed_successfully",
                    "pid": self.training_process.pid,
                    "stdout": stdout.decode('utf-8'),
                }
            else:
                return {
                    "status": "failed",
                    "pid": self.training_process.pid,
                    "returncode": self.training_process.returncode,
                    "stderr": stderr.decode('utf-8'),
                }

    def get_latest_adapter(self) -> Optional[Path]:
        """Trouve le chemin du dernier adaptateur LoRA entraîné."

        Les adaptateurs sont supposés être stockés dans des sous-répertoires
        nommés 'checkpoint-N' où N est un numéro d'étape.

        Returns:
            Le chemin `Path` vers le répertoire du dernier adaptateur,
            ou None si aucun adaptateur n'est trouvé.
        """
        try:
            # Liste tous les sous-répertoires qui ressemblent à des checkpoints.
            adapters = [p for p in ADAPTERS_OUTPUT_DIR.iterdir() if p.is_dir() and p.name.startswith("checkpoint-")]
            if not adapters:
                logger.info(f"Aucun adaptateur trouvé dans {ADAPTERS_OUTPUT_DIR}.")
                return None
            # Trie les adaptateurs par numéro de checkpoint pour trouver le plus récent.
            latest_adapter = max(adapters, key=lambda p: int(p.name.split('-')[-1]))
            logger.info(f"Dernier adaptateur trouvé : {latest_adapter}.")
            return latest_adapter
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Erreur lors de la recherche du dernier adaptateur : {e}")
            return None


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def main():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        evolution = PersonalityEvolution()

        # 1. Ajouter un nouvel exemple d'entraînement.
        new_example = {
            "instruction": "Reformule cette phrase de manière plus empathique.",
            "input": "Le ticket est fermé car le problème n'est pas reproductible.",
            "output": "Je comprends votre frustration. Pour l'instant, nous n'avons pas pu reproduire le problème pour le corriger, mais nous restons attentifs si de nouvelles informations apparaissent."
        }
        print("\n--- Ajout d'un exemple d'entraînement ---")
        await evolution.add_training_example(new_example)

        # 2. Déclencher un cycle de fine-tuning (simulation).
        # Pour la démo, nous allons créer un script factice si nécessaire.
        if not TRAINING_SCRIPT_PATH.exists():
            TRAINING_SCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
            TRAINING_SCRIPT_PATH.write_text("""
import time
import sys
print("Simulating a successful training run...")
time.sleep(1)
print("Training complete.")
sys.exit(0)
""")
            print(f"Script d'entraînement factice créé à : {TRAINING_SCRIPT_PATH}")
        
        print("\n--- Déclenchement du Fine-Tuning ---")
        start_result = await evolution.trigger_finetuning_cycle(min_new_examples=1)
        logging.info(f"Résultat du déclenchement : {start_result}")

        if start_result["status"] == "started":
            print("Attente de la fin du processus d'entraînement (simulation)...")
            # Attendre que le processus se termine.
            while True:
                status_result = await evolution.get_training_status()
                logging.info(f"Statut actuel : {status_result['status']}")
                if status_result['status'] not in ["running", "not_running"]:
                    break
                await asyncio.sleep(1)
            logging.info(f"Statut final de l'entraînement : {status_result}")

        # 3. Trouver le dernier adaptateur (simulation).
        print("\n--- Recherche du dernier adaptateur ---")
        # Simuler la création de répertoires d'adaptateurs.
        (ADAPTERS_OUTPUT_DIR / "checkpoint-100").mkdir(parents=True, exist_ok=True)
        (ADAPTERS_OUTPUT_DIR / "checkpoint-200").mkdir(parents=True, exist_ok=True)
        latest = evolution.get_latest_adapter()
        logging.info(f"Dernier adaptateur trouvé : {latest}")
        assert latest and latest.name == "checkpoint-200"

        print("Démonstration de PersonalityEvolution terminée.")

        # Nettoyage des fichiers et répertoires temporaires.
        if TRAINING_DATA_PATH.exists():
            TRAINING_DATA_PATH.unlink()
        if TRAINING_SCRIPT_PATH.exists():
            TRAINING_SCRIPT_PATH.unlink()
        if ADAPTERS_OUTPUT_DIR.exists():
            import shutil
            shutil.rmtree(ADAPTERS_OUTPUT_DIR)

    asyncio.run(main())