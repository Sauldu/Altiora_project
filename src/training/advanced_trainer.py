# src/training/advanced_trainer.py
import argparse

import torch
import wandb
from datasets import Dataset, load_dataset
from peft import LoraConfig, get_peft_model, TaskType
from transformers import (
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer
)


class AltioraModelTrainer:
    """Trainer avancé pour Qwen3 et Starcoder2"""

    def __init__(self, model_name: str, task: str):
        self.model_name = model_name
        self.task = task
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Configuration LoRA pour efficacité mémoire
        self.lora_config = LoraConfig(
            r=16,  # rank
            lora_alpha=32,
            target_modules=["q_proj", "v_proj"],
            lora_dropout=0.1,
            bias="none",
            task_type=TaskType.CAUSAL_LM
        )

    def prepare_model(self):
        """Préparer modèle avec optimisations"""
        # Charger modèle de base
        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            load_in_8bit=True,  # Quantization
            device_map="auto"
        )

        # Appliquer LoRA
        model = get_peft_model(model, self.lora_config)
        model.print_trainable_parameters()

        # Activation du gradient checkpointing
        model.gradient_checkpointing_enable()

        # Activation du mixed precision training
        model.half()

        return model

    def train(self, train_dataset: Dataset, eval_dataset: Dataset):
        """Entraînement avec monitoring W&B"""
        wandb.init(project="altiora", name=f"{self.task}_{self.model_name}")

        training_args = TrainingArguments(
            output_dir=f"./models/{self.task}",
            num_train_epochs=3,
            per_device_train_batch_size=4,
            gradient_accumulation_steps=4,
            warmup_steps=100,
            logging_steps=10,
            save_strategy="epoch",
            evaluation_strategy="epoch",
            fp16=True,  # Mixed precision
            report_to="wandb",
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False
        )

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            compute_metrics=self.compute_metrics
        )

        trainer.train()
        trainer.save_model()
        logger.info(f"Training complete. Model saved to: {training_args.output_dir}")

    @staticmethod
    def compute_metrics(eval_pred):
        """Calcul des métriques d'évaluation"""
        logits, labels = eval_pred
        predictions = torch.argmax(logits, dim=-1)
        accuracy = (predictions == labels).sum().item() / labels.size(0)
        return {"accuracy": accuracy}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default="Qwen/Qwen-3B", help="Nom du modèle pré-entraîné")
    parser.add_argument("--task", type=str, default="qa", help="Tâche à effectuer")
    parser.add_argument("--train_dataset", type=str, required=True, help="Chemin vers le dataset d'entraînement")
    parser.add_argument("--eval_dataset", type=str, required=True, help="Chemin vers le dataset de validation")
    args = parser.parse_args()

    trainer = AltioraModelTrainer(model_name=args.model_name, task=args.task)
    train_dataset = load_dataset("json", data_files=args.train_dataset, split="train")
    eval_dataset = load_dataset("json", data_files=args.eval_dataset, split="validation")

    trainer.train(train_dataset, eval_dataset)
