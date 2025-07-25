# src/models/qwen3/fine_tuning.py
"""Module de gestion du fine-tuning et de l'adaptation locale de Qwen3.

Ce module fournit des outils pour :
- Préparer des jeux de données d'entraînement à partir de spécifications brutes.
- Lancer des entraînements LoRA (Low-Rank Adaptation) sur CPU ou GPU via Ollama CLI.
- Évaluer rapidement les modèles fine-tunés.
- Gérer (sauvegarder, charger, lister, supprimer) les adaptateurs LoRA.
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import yaml

logger = logging.getLogger(__name__)


class QwenFineTuningManager:
    """Gestionnaire complet pour le fine-tuning du modèle Qwen3."""

    def __init__(self, base_model: str = "qwen3:32b-q4_K_M"):
        """Initialise le gestionnaire de fine-tuning.

        Args:
            base_model: Le nom du modèle de base Qwen3 à fine-tuner (doit être disponible dans Ollama).
        """
        self.base_model = base_model
        self.data_dir = Path("data/training")
        self.output_dir = Path("models/qwen3/adapters")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Préparation du dataset
    # ------------------------------------------------------------------

    def prepare_dataset(self, raw_data: List[Dict[str, Any]], output_file: str = "train.jsonl") -> Path:
        """Convertit des spécifications brutes en un dataset JSONL compatible avec Ollama.

        Le format attendu pour chaque ligne du fichier JSONL est :
        `{"instruction": "...", "input": "...", "output": "..."}`.

        Args:
            raw_data: Une liste de dictionnaires, où chaque dictionnaire contient
                      'spec' (la spécification brute) et 'tests' (les scénarios de test attendus).
            output_file: Le nom du fichier JSONL de sortie.

        Returns:
            Le chemin d'accès au fichier dataset généré.

        Raises:
            IOError, OSError: En cas d'erreur lors de l'écriture du fichier.
        """
        dataset_path = self.data_dir / output_file
        dataset_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(dataset_path, "w", encoding="utf-8") as f:
                for item in raw_data:
                    prompt = self._build_prompt(item["spec"])
                    response = self._build_response(item["tests"])
                    f.write(json.dumps({"instruction": prompt, "input": "", "output": response}, ensure_ascii=False) + "\n")

            logger.info(f"Dataset créé : {dataset_path} ({len(raw_data)} lignes).")
            return dataset_path
        except (IOError, OSError) as e:
            logger.error(f"Erreur lors de la préparation du dataset {dataset_path}: {e}")
            raise

    @staticmethod
    def _build_prompt(spec: str) -> str:
        """Construit le prompt d'entraînement standardisé pour Qwen3."""
        return f"""### Spécification :
{spec}

### Tâche :
Extraire les scénarios de test au format JSON.
"""

    @staticmethod
    def _build_response(tests: List[Dict[str, Any]]) -> str:
        """Construit la réponse attendue standardisée au format JSON."""
        return json.dumps({"scenarios": tests}, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Entraînement LoRA
    # ------------------------------------------------------------------

    def train_lora(
            self,
            dataset_path: Path,
            adapter_name: str,
            epochs: int = 3,
            learning_rate: float = 1e-4,
            device: str = "cpu"
    ) -> Path:
        """Lance l'entraînement LoRA via l'interface CLI d'Ollama.

        Cette méthode utilise la commande `ollama create` avec un Modelfile
        pour effectuer le fine-tuning. Elle est compatible avec l'entraînement
        sur CPU ou GPU local.

        Args:
            dataset_path: Le chemin vers le fichier JSONL du dataset d'entraînement.
            adapter_name: Le nom de l'adaptateur LoRA à créer.
            epochs: Le nombre d'époques d'entraînement.
            learning_rate: Le taux d'apprentissage.
            device: Le périphérique d'entraînement ('cpu' ou 'gpu').

        Returns:
            Le chemin d'accès au répertoire de l'adaptateur LoRA créé.

        Raises:
            subprocess.CalledProcessError: Si la commande Ollama échoue.
            RuntimeError: Si le fine-tuning échoue.
        """
        adapter_dir = self.output_dir / adapter_name
        adapter_dir.mkdir(exist_ok=True) # Crée le répertoire de l'adaptateur.

        # Crée un fichier de configuration temporaire pour Ollama.
        config = {
            "model": self.base_model,
            "dataset": str(dataset_path),
            "output": str(adapter_dir),
            "epochs": epochs,
            "learning_rate": learning_rate,
            "device": device,
            "format": "jsonl"
        }

        config_path = adapter_dir / "config.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f)

        # Construit la commande Ollama.
        cmd = [
            "ollama", "create", adapter_name,
            "--modelfile", str(config_path),
            "--path", str(adapter_dir)
        ]

        try:
            logger.info(f"Lancement de l'entraînement LoRA pour {adapter_name}...")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8')
            logger.info(f"Sortie standard de Ollama :\n{result.stdout}")
            if result.stderr:
                logger.warning(f"Erreurs/Avertissements de Ollama :\n{result.stderr}")
            logger.info(f"Adaptateur LoRA créé avec succès : {adapter_dir}")
            return adapter_dir
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur lors de l'entraînement LoRA : {e.stderr}")
            raise RuntimeError("Le fine-tuning a échoué.") from e
        except FileNotFoundError:
            logger.error("La commande 'ollama' n'a pas été trouvée. Assurez-vous qu'Ollama est installé et dans le PATH.")
            raise RuntimeError("Ollama CLI non trouvé.")

    # ------------------------------------------------------------------
    # Évaluation rapide
    # ------------------------------------------------------------------

    @staticmethod
    def evaluate(test_dataset: Path, adapter_name: str) -> Dict[str, float]:
        """Effectue une évaluation simple de l'adaptateur fine-tuné.

        Cette méthode simule une évaluation en comptant le nombre de réponses
        valides (contenant des scénarios) dans un dataset de test.

        Args:
            test_dataset: Le chemin vers le fichier JSONL du dataset de test.
            adapter_name: Le nom de l'adaptateur à évaluer.

        Returns:
            Un dictionnaire contenant le score de précision et le nombre d'échantillons.
        """
        total = 0
        valid = 0
        try:
            with open(test_dataset, "r", encoding="utf-8") as f:
                for line in f:
                    total += 1
                    try:
                        data = json.loads(line)
                        # Vérifie si la sortie contient une clé 'scenarios'.
                        if "scenarios" in data.get("output", ""):
                            valid += 1
                    except json.JSONDecodeError:
                        pass # Ignore les lignes JSON mal formées.
        except (IOError, OSError) as e:
            logger.error(f"Erreur lors de la lecture du dataset de test {test_dataset}: {e}")
            return {"accuracy": 0.0, "samples": 0}

        score = valid / total if total else 0.0
        logger.info(f"Évaluation de l'adaptateur {adapter_name} : {score:.2%}")
        return {"accuracy": score, "samples": total}

    # ------------------------------------------------------------------
    # Gestion des adaptateurs
    # ------------------------------------------------------------------

    def list_adapters(self) -> List[str]:
        """Liste les noms de tous les adaptateurs LoRA disponibles localement."""
        return [d.name for d in self.output_dir.iterdir() if d.is_dir()]

    def load_adapter(self, adapter_name: str) -> Optional[Path]:
        """Retourne le chemin d'accès à un adaptateur LoRA spécifique."

        Args:
            adapter_name: Le nom de l'adaptateur à charger.

        Returns:
            Le chemin `Path` vers l'adaptateur si trouvé, sinon None.
        """
        path = self.output_dir / adapter_name
        return path if path.exists() else None

    def delete_adapter(self, adapter_name: str) -> bool:
        """Supprime un adaptateur LoRA et son répertoire associé."

        Args:
            adapter_name: Le nom de l'adaptateur à supprimer.

        Returns:
            True si l'adaptateur a été supprimé, False sinon.
        """
        path = self.output_dir / adapter_name
        if path.exists():
            import shutil
            try:
                shutil.rmtree(path)
                logger.info(f"Adaptateur supprimé : {path}")
                return True
            except Exception as e:
                logger.error(f"Erreur lors de la suppression de l'adaptateur {path}: {e}")
                return False
        return False

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def generate_training_report(self, adapter_name: str) -> Dict[str, Any]:
        """Génère un rapport synthétique sur un adaptateur entraîné."

        Args:
            adapter_name: Le nom de l'adaptateur pour lequel générer le rapport.

        Returns:
            Un dictionnaire contenant les métadonnées de l'adaptateur.
        """
        adapter_path = self.output_dir / adapter_name
        if not adapter_path.exists():
            return {"error": "Adaptateur non trouvé"}

        return {
            "adapter": adapter_name,
            "created": datetime.fromtimestamp(adapter_path.stat().st_mtime).isoformat(),
            "files": [str(p.name) for p in adapter_path.iterdir()],
            "base_model": self.base_model,
        }


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    manager = QwenFineTuningManager()

    # 1. Préparation d'un dataset de démonstration.
    sample_raw_data = [
        {
            "spec": "La page de connexion doit permettre aux utilisateurs de se connecter avec un email et un mot de passe.",
            "tests": [
                {"titre": "Connexion réussie", "objectif": "Vérifier la connexion valide"},
                {"titre": "Mot de passe incorrect", "objectif": "Vérifier le message d'erreur"}
            ]
        },
        {
            "spec": "Le formulaire d'inscription doit valider l'email et le mot de passe.",
            "tests": [
                {"titre": "Inscription valide", "objectif": "Vérifier l'inscription réussie"}
            ]
        }
    ]
    dataset_file = manager.prepare_dataset(sample_raw_data, "demo_train.jsonl")

    # 2. Lancement d'un entraînement LoRA (simulé).
    adapter_name = "qwen3-sfd-adapter-v1"
    try:
        # Note: Pour une exécution réelle, Ollama doit être installé et configuré.
        # Cette partie peut échouer si `ollama` n'est pas dans le PATH.
        trained_adapter_path = manager.train_lora(
            dataset_path=dataset_file,
            adapter_name=adapter_name,
            epochs=1, # Réduit pour la démo.
            device="cpu"
        )
        logging.info(f"Adaptateur entraîné : {trained_adapter_path}")
    except RuntimeError as e:
        logging.error(f"Impossible de lancer l'entraînement LoRA : {e}")
        logging.info("Passe l'étape d'entraînement pour la démonstration.")
        trained_adapter_path = manager.load_adapter(adapter_name) # Tente de charger si déjà existant.

    # 3. Évaluation de l'adaptateur.
    if trained_adapter_path:
        evaluation_results = manager.evaluate(dataset_file, adapter_name)
        logging.info(f"Résultats d'évaluation : {evaluation_results}")

        # 4. Génération d'un rapport.
        report = manager.generate_training_report(adapter_name)
        logging.info(f"Rapport d'entraînement : {json.dumps(report, indent=2, ensure_ascii=False)}")

        # 5. Suppression de l'adaptateur (optionnel).
        # manager.delete_adapter(adapter_name)
        # logging.info(f"Adaptateur {adapter_name} supprimé.")
    else:
        logging.warning("Aucun adaptateur entraîné ou chargé pour la démonstration.")