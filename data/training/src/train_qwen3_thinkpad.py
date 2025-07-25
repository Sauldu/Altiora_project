# data/training/src/train_qwen3_thinkpad.py
"""Script d'entraînement pour le fine-tuning du modèle Qwen3-32B-Q4_K_M.

Ce script est optimisé pour l'entraînement sur des systèmes avec 32 Go de RAM
(comme un Intel i5 de 13ème génération), en utilisant des techniques comme
la quantification 4-bit, LoRA (Low-Rank Adaptation), le gradient checkpointing
et le mixed precision training pour une utilisation efficace des ressources CPU.
"""

import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import torch
from datasets import load_dataset, Dataset
from peft import LoraConfig, get_peft_model, TaskType
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class Qwen3Config:
    """Configuration pour l'entraînement du modèle Qwen3.

    Les paramètres peuvent être définis via des variables d'environnement ou des valeurs par défaut.
    """
    model_name: str = os.getenv("MODEL_NAME", "Qwen/Qwen3-32B-q4_K_M")
    output_dir: str = os.getenv("OUTPUT_DIR", "./models/qwen3-finetuned")
    lora_r: int = int(os.getenv("LORA_R", "16"))
    lora_alpha: int = int(os.getenv("LORA_ALPHA", "32"))
    lora_dropout: float = float(os.getenv("LORA_DROPOUT", "0.1"))
    epochs: int = int(os.getenv("EPOCHS", "3"))
    batch_size: int = int(os.getenv("BATCH_SIZE", "1"))
    grad_accum: int = int(os.getenv("GRAD_ACCUM", "32")) # Accumulation de gradient.
    lr: float = float(os.getenv("LR", "2e-4")) # Taux d'apprentissage.
    max_seq_len: int = int(os.getenv("MAX_SEQ_LEN", "512")) # Longueur maximale de séquence.
    num_workers: int = int(os.getenv("NUM_WORKERS", "4")) # Nombre de workers pour le chargement des données.


class Qwen3Trainer:
    """Classe d'entraînement pour le fine-tuning du modèle Qwen3."""

    def __init__(self, cfg: Qwen3Config) -> None:
        """Initialise l'entraîneur.

        Args:
            cfg: L'objet de configuration `Qwen3Config`.
        """
        self.config_path = Path("configs/training_config.json") # Chemin vers un fichier de configuration JSON.
        self.config = self._load_config() # Charge la configuration JSON.
        self.cfg = cfg
        # Détermine le périphérique d'entraînement (CPU est forcé ici pour l'optimisation ThinkPad).
        self.device = torch.device("cpu")
        self._check_ram() # Vérifie la RAM disponible.

    def _load_config(self) -> Dict[str, Any]:
        """Charge la configuration d'entraînement depuis un fichier JSON.

        Returns:
            Un dictionnaire contenant la configuration.
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Fichier de configuration non trouvé à {self.config_path}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Erreur de décodage JSON depuis {self.config_path}")
            return {}

    @staticmethod
    def _check_ram() -> None:
        """Vérifie la RAM disponible et loggue un avertissement si elle est faible.

        Nécessite la bibliothèque `psutil`.
        """
        try:
            import psutil
            gb_available = psutil.virtual_memory().available / (1024 ** 3)
            if gb_available < 20:
                logger.warning("RAM disponible (%.1f Go) faible – envisagez de fermer des applications.", gb_available)
        except ImportError:
            logger.warning("La bibliothèque 'psutil' n'est pas installée. Impossible de vérifier la RAM.")

    def _load_model_tokenizer(self) -> None:
        """Charge le modèle de base et le tokenizer, et applique les optimisations LoRA.

        Le modèle est chargé en 8-bit pour réduire l'utilisation de la mémoire.
        """
        logger.info("Chargement du modèle %s...", self.cfg.model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.cfg.model_name,
            trust_remote_code=True, # Permet le chargement de code distant (nécessaire pour certains modèles).
        )
        self.tokenizer.pad_token = self.tokenizer.eos_token # Définit le token de padding.

        self.model = AutoModelForCausalLM.from_pretrained(
            self.cfg.model_name,
            device_map={"": self.device}, # Force le modèle sur le CPU.
            torch_dtype=torch.float32, # Utilise float32 pour la précision.
            trust_remote_code=True,
            low_cpu_mem_usage=True, # Optimisation de la mémoire CPU.
        )

        # Configuration LoRA et application au modèle.
        lora_config = LoraConfig(
            r=self.cfg.lora_r,
            lora_alpha=self.cfg.lora_alpha,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], # Modules cibles pour LoRA.
            lora_dropout=self.cfg.lora_dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters() # Affiche les paramètres entraînés par LoRA.

        # Activation du gradient checkpointing pour réduire l'utilisation de la mémoire.
        self.model.gradient_checkpointing_enable()

        # Activation du mixed precision training (entraînement en précision mixte).
        # Utilise des float16 pour les calculs, réduisant la mémoire et accélérant sur certains GPU.
        # Note: `self.model.half()` est une optimisation pour GPU, peut ne pas être optimale sur CPU.
        self.model.half()

    def _load_dataset(self, path: Path) -> Dataset:
        """Charge le dataset d'entraînement et le formate pour le modèle.

        Args:
            path: Le chemin vers le fichier JSONL du dataset.

        Returns:
            Un objet `Dataset` prêt pour l'entraînement.
        """
        # Charge le dataset en streaming pour gérer de grands fichiers.
        ds = load_dataset(
            "json",
            data_files=str(path),
            streaming=True,
            cache_dir="./cache"
        )

        def fmt(sample: Dict[str, Any]) -> Dict[str, str]:
            """Formate un échantillon de données pour le modèle Qwen3."""
            # Format spécifique pour Qwen3 avec des tokens de système, utilisateur et assistant.
            return {
                "text": (
                    f"<|im_start|>system\nTu es un expert en automatisation de tests.<|im_end|>\n"
                    f"<|im_start|>user\n{sample['instruction']}\n{sample.get('input', '')}<|im_end|>\n"
                    f"<|im_start|>assistant\n{sample['output']}<|im_end|>"
                )
            }

        # Applique le formatage et la tokenisation au dataset.
        ds = ds.map(fmt)
        return ds.map(
            lambda x: self.tokenizer(
                x["text"],
                padding="max_length",
                truncation=True,
                max_length=self.cfg.max_seq_len,
            ),
            batched=True,
            remove_columns=ds.column_names, # Supprime les colonnes originales après tokenisation.
        )

    def train(self, dataset_path: Path) -> None:
        """Lance le processus d'entraînement du modèle.

        Args:
            dataset_path: Le chemin vers le fichier JSONL du dataset d'entraînement.
        """
        self._load_model_tokenizer()
        ds = self._load_dataset(dataset_path)

        # Configure les arguments d'entraînement pour le Trainer de Hugging Face.
        args = TrainingArguments(
            output_dir=self.cfg.output_dir,
            num_train_epochs=self.cfg.epochs,
            per_device_train_batch_size=self.cfg.batch_size,
            gradient_accumulation_steps=self.cfg.grad_accum,
            learning_rate=self.cfg.lr,
            optim="adamw_torch", # Optimiseur AdamW.
            logging_steps=10,
            save_steps=100,
            save_total_limit=3,
            report_to="tensorboard", # Pour le suivi avec TensorBoard.
            dataloader_num_workers=self.cfg.num_workers,
            remove_unused_columns=False,
            fp16=True,  # Active le mixed precision training.
            bf16=False, # Désactive bfloat16.
            tf32=False, # Désactive tf32.
            dataloader_pin_memory=False, # Désactive le pin memory pour le dataloader.
        )

        # Initialise le Trainer.
        trainer = Trainer(
            model=self.model,
            args=args,
            train_dataset=ds,
            data_collator=DataCollatorForLanguageModeling(
                tokenizer=self.tokenizer, mlm=False # Data collator pour la modélisation du langage.
            ),
            tokenizer=self.tokenizer,
        )

        logger.info("Démarrage de l'entraînement...")
        trainer.train()
        trainer.save_model() # Sauvegarde le modèle fine-tuné.
        logger.info("Entraînement terminé. Modèle sauvegardé dans : %s", self.cfg.output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lance l'entraînement du modèle Qwen3.")
    parser.add_argument("--dataset", required=True, type=Path, help="Chemin vers le dataset JSONL d'entraînement.")
    parser.add_argument("--output", type=Path, default=Path("./models/qwen3-finetuned"), help="Répertoire de sortie pour le modèle entraîné.")
    args = parser.parse_args()

    # Crée une instance de configuration à partir des arguments CLI.
    config = Qwen3Config(output_dir=str(args.output))
    trainer = Qwen3Trainer(config)
    trainer.train(args.dataset)