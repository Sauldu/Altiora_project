# src/training/advanced_trainer.py
"""Module pour l'entraînement avancé (fine-tuning) des modèles de langage (LLMs).

Ce module fournit une classe `AltioraModelTrainer` pour le fine-tuning de
modèles comme Qwen3 et Starcoder2. Il utilise des techniques d'optimisation
de la mémoire comme LoRA (Low-Rank Adaptation) et le gradient checkpointing,
ainsi que le mixed precision training pour améliorer l'efficacité de
l'entraînement sur des ressources limitées (CPU ou GPU).
"""

import argparse
import logging

import torch
import wandb
from datasets import Dataset, load_dataset
from peft import LoraConfig, get_peft_model, TaskType
from transformers import (
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    AutoTokenizer # Ajouté pour la tokenisation du dataset
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class AltioraModelTrainer:
    """Entraîneur avancé pour le fine-tuning de modèles de langage (LLMs).

    Prend en charge les optimisations pour l'entraînement efficace sur CPU/GPU.
    """

    def __init__(self, model_name: str, task: str):
        """Initialise l'entraîneur de modèle.

        Args:
            model_name: Le nom du modèle pré-entraîné à charger (ex: "Qwen/Qwen-3B").
            task: La tâche pour laquelle le modèle est entraîné (ex: "qa", "code_gen").
        """
        self.model_name = model_name
        self.task = task
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Entraîneur initialisé. Utilisation du périphérique : {self.device}")

        # Configuration LoRA (Low-Rank Adaptation) pour l'efficacité mémoire.
        # LoRA permet d'entraîner un petit nombre de paramètres supplémentaires
        # au lieu de l'ensemble du modèle, réduisant ainsi les besoins en mémoire et en calcul.
        self.lora_config = LoraConfig(
            r=16,  # Le rang des matrices LoRA. Une valeur plus élevée augmente la capacité d'apprentissage.
            lora_alpha=32, # Facteur de mise à l'échelle pour les poids LoRA.
            target_modules=["q_proj", "v_proj"], # Modules du modèle où appliquer LoRA (typiquement les couches d'attention).
            lora_dropout=0.1, # Taux de dropout pour les couches LoRA.
            bias="none", # Ne pas entraîner les biais.
            task_type=TaskType.CAUSAL_LM # Type de tâche pour le modèle (modélisation du langage causal).
        )

    def prepare_model(self):
        """Prépare le modèle de base avec les optimisations LoRA et de mémoire."

        Returns:
            Le modèle préparé pour l'entraînement.
        """
        logger.info(f"Chargement du modèle de base : {self.model_name}...")
        # Charge le modèle de base pré-entraîné.
        # `load_in_8bit=True` active la quantification 8-bit pour réduire l'utilisation de la mémoire.
        # `device_map="auto"` distribue automatiquement le modèle sur les périphériques disponibles.
        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            load_in_8bit=True,
            device_map="auto"
        )
        logger.info("Modèle de base chargé.")

        # Applique l'adaptateur LoRA au modèle de base.
        model = get_peft_model(model, self.lora_config)
        # Affiche le nombre de paramètres entraînés (LoRA) par rapport au total.
        model.print_trainable_parameters()

        # Active le gradient checkpointing pour réduire l'utilisation de la mémoire GPU
        # au prix d'une légère augmentation du temps de calcul.
        model.gradient_checkpointing_enable()

        # Active le mixed precision training (entraînement en précision mixte).
        # Utilise des float16 pour les calculs, réduisant la mémoire et accélérant sur certains GPU.
        model.half()

        return model

    def train(self, train_dataset: Dataset, eval_dataset: Dataset):
        """Lance le processus d'entraînement du modèle avec monitoring Weights & Biases."

        Args:
            train_dataset: Le jeu de données d'entraînement.
            eval_dataset: Le jeu de données de validation.
        """
        logger.info("Démarrage de l'entraînement...")
        # Initialise une session Weights & Biases pour le suivi de l'entraînement.
        wandb.init(project="altiora", name=f"{self.task}_{self.model_name}")

        # Prépare le modèle avant de le passer au Trainer.
        self.model = self.prepare_model()

        # Configure les arguments d'entraînement.
        training_args = TrainingArguments(
            output_dir=f"./models/{self.task}", # Répertoire de sortie pour les checkpoints et le modèle final.
            num_train_epochs=3, # Nombre d'époques d'entraînement.
            per_device_train_batch_size=4, # Taille du batch par périphérique (GPU/CPU).
            gradient_accumulation_steps=4, # Accumule les gradients sur plusieurs étapes pour simuler un plus grand batch.
            warmup_steps=100, # Nombre d'étapes de warm-up pour le taux d'apprentissage.
            logging_steps=10, # Fréquence de logging des métriques.
            save_strategy="epoch", # Stratégie de sauvegarde du modèle (à chaque époque).
            evaluation_strategy="epoch", # Stratégie d'évaluation (à chaque époque).
            fp16=True,  # Active le mixed precision training (float16).
            report_to="wandb", # Intègre le reporting à Weights & Biases.
            load_best_model_at_end=True, # Charge le meilleur modèle (basé sur `metric_for_best_model`) à la fin.
            metric_for_best_model="eval_loss", # Métrique utilisée pour déterminer le meilleur modèle.
            greater_is_better=False # Pour eval_loss, une valeur plus petite est meilleure.
        )

        # Initialise le tokenizer.
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)

        # Crée l'instance du Trainer.
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            compute_metrics=self.compute_metrics,
            tokenizer=tokenizer # Le tokenizer est nécessaire pour le Trainer.
        )

        # Lance l'entraînement.
        trainer.train()
        # Sauvegarde le modèle final.
        trainer.save_model()
        logger.info(f"Entraînement terminé. Modèle sauvegardé dans : {training_args.output_dir}")

    @staticmethod
    def compute_metrics(eval_pred: tuple) -> Dict[str, float]:
        """Calcule les métriques d'évaluation à partir des prédictions du modèle."

        Args:
            eval_pred: Un tuple contenant les logits et les labels réels.

        Returns:
            Un dictionnaire de métriques (ex: {"accuracy": 0.95}).
        """
        logits, labels = eval_pred
        # Pour les tâches de modélisation du langage, la précision peut être calculée
        # en comparant les jetons prédits (argmax des logits) aux jetons réels.
        predictions = torch.argmax(torch.tensor(logits), dim=-1)
        # Assurez-vous que les labels et les prédictions ont la même forme et sont comparables.
        # Cette implémentation est très basique et peut nécessiter une adaptation
        # en fonction de la tâche spécifique et du format des données.
        accuracy = (predictions == torch.tensor(labels)).sum().item() / labels.size
        return {"accuracy": accuracy}


# ------------------------------------------------------------------
# Point d'entrée CLI pour l'entraînement
# ------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lance l'entraînement d'un modèle de langage.")
    parser.add_argument("--model_name", type=str, default="Qwen/Qwen-3B", help="Nom du modèle pré-entraîné à utiliser.")
    parser.add_argument("--task", type=str, default="qa", help="Tâche pour laquelle le modèle est entraîné (ex: 'qa', 'code_gen').")
    parser.add_argument("--train_dataset", type=str, required=True, help="Chemin vers le dataset d'entraînement (format JSON). Ex: 'data/training/train.jsonl'.")
    parser.add_argument("--eval_dataset", type=str, required=True, help="Chemin vers le dataset de validation (format JSON). Ex: 'data/training/eval.jsonl'.")
    args = parser.parse_args()

    logger.info(f"Démarrage de l'entraînement pour le modèle {args.model_name} sur la tâche {args.task}.")

    trainer = AltioraModelTrainer(model_name=args.model_name, task=args.task)
    
    # Charge les datasets. Assurez-vous que les fichiers sont au format JSON Lines.
    try:
        train_dataset = load_dataset("json", data_files=args.train_dataset, split="train")
        eval_dataset = load_dataset("json", data_files=args.eval_dataset, split="train") # Utilise 'train' pour la démo si pas de split 'validation'.
    except Exception as e:
        logger.error(f"Erreur lors du chargement des datasets : {e}. Assurez-vous que les chemins sont corrects et les fichiers au format JSON Lines.")
        exit(1)

    # Lance l'entraînement.
    trainer.train(train_dataset, eval_dataset)
    logger.info("Script d'entraînement terminé.")