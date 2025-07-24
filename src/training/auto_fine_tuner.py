# src/training/auto_fine_tuner.py
import mlflow
import torch
from datasets import load_dataset
from torch.cuda.amp import autocast, GradScaler
from transformers import AutoModelForCausalLM


class AutoFineTuner:
    def __init__(self, base_model: str, output_dir: str):
        self.base_model = base_model
        self.output_dir = output_dir
        mlflow.set_tracking_uri("http://localhost:5000")
        self.model = self._load_model()

    def _load_model(self):
        """Charger le modèle de base"""
        model = AutoModelForCausalLM.from_pretrained(self.base_model)
        model.gradient_checkpointing_enable()  # Activation du gradient checkpointing
        model.half()  # Activation du mixed precision training
        return model

    @staticmethod
    def prepare_dataset(data_path: str):
        """Prépare le dataset avec validation automatique"""
        dataset = load_dataset("json", data_files=data_path, split="train")
        train_test_split = dataset.train_test_split(test_size=0.2)
        train_val_split = train_test_split['train'].train_test_split(test_size=0.1)
        return {
            'train': train_val_split['train'],
            'val': train_val_split['test'],
            'test': train_test_split['test']
        }

    def train_with_tracking(self, dataset, hyperparams):
        """Entraînement avec tracking MLflow"""
        scaler = GradScaler()
        with mlflow.start_run():
            mlflow.log_params(hyperparams)

            for epoch in range(hyperparams['epochs']):
                train_loss = self.train_epoch(dataset['train'], scaler)
                val_loss = self.validate(dataset['val'], scaler)

                mlflow.log_metrics({
                    'train_loss': train_loss,
                    'val_loss': val_loss
                }, step=epoch)

                if self.should_early_stop(val_loss):
                    break

            mlflow.pytorch.log_model(self.model, "model")

    def train_epoch(self, train_dataset, scaler):
        """Entraînement pour une époque"""
        self.model.train()
        total_loss = 0
        for batch in train_dataset:
            with autocast():
                outputs = self.model(**batch)
                loss = outputs.loss
            scaler.scale(loss).backward()
            scaler.step(self.optimizer)
            scaler.update()
            total_loss += loss.item()
        return total_loss / len(train_dataset)

    def validate(self, val_dataset, scaler):
        """Validation du modèle"""
        self.model.eval()
        total_loss = 0
        with torch.no_grad():
            for batch in val_dataset:
                with autocast():
                    outputs = self.model(**batch)
                    loss = outputs.loss
                total_loss += loss.item()
        return total_loss / len(val_dataset)

    @staticmethod
    def should_early_stop(val_loss):
        """Décider si on doit arrêter l'entraînement prématurément"""
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--base_model", type=str, default="Qwen/Qwen-3B", help="Nom du modèle pré-entraîné")
    parser.add_argument("--output_dir", type=str, default="./models/finetuned", help="Répertoire de sortie")
    parser.add_argument("--data_path", type=str, required=True, help="Chemin vers le dataset")
    args = parser.parse_args()

    tuner = AutoFineTuner(base_model=args.base_model, output_dir=args.output_dir)
    dataset = tuner.prepare_dataset(args.data_path)
    hyperparams = {
        'epochs': 3,
        'learning_rate': 2e-4,
        'batch_size': 4
    }
    tuner.train_with_tracking(dataset, hyperparams)
