import pytest
from pathlib import Path
from data.training.src.train_qwen3_thinkpad import Qwen3Trainer, Qwen3Config
import json
import logging

logger = logging.getLogger(__name__)

"""Tests d'intégration pour le fine-tuning des modèles de langage.

Ce module contient des tests qui vérifient le processus de fine-tuning
des modèles (notamment Qwen3) avec des adaptateurs LoRA, en se concentrant
sur l'efficacité de la mémoire et la capacité à s'exécuter sur CPU.
"""


@pytest.mark.slow # Marque le test comme lent, car il implique un entraînement de modèle.
@pytest.mark.asyncio
async def test_lora_training_cpu(tmp_path: Path):
    """Teste l'entraînement LoRA sur CPU avec des contraintes de mémoire."

    Ce test simule un entraînement de fine-tuning pour Qwen3 en utilisant
    un petit dataset et des paramètres optimisés pour le CPU, afin de vérifier
    que le processus se déroule sans erreur et produit un modèle entraîné.

    Args:
        tmp_path: Fixture Pytest fournissant un répertoire temporaire pour les fichiers.
    """
    # Crée un fichier de dataset minimal pour l'entraînement.
    test_data = [
        {"instruction": "Quelle est la capitale de la France ?", "input": "", "output": "Paris"},
        {"instruction": "Qui a écrit 'Les Misérables' ?", "input": "", "output": "Victor Hugo"}
    ]
    dataset_path = tmp_path / "test_dataset.jsonl"
    with open(dataset_path, "w", encoding="utf-8") as f:
        for item in test_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    logger.info(f"Dataset de test créé à : {dataset_path}")

    # Configure le trainer avec des paramètres optimisés pour le CPU et la mémoire.
    # Ces paramètres sont réduits pour accélérer le test.
    config = Qwen3Config(
        output_dir=str(tmp_path / "qwen3_finetuned"),
        lora_r=4, # Rang LoRA très faible pour un entraînement rapide.
        lora_alpha=8,
        epochs=1, # Une seule époque pour le test.
        batch_size=1,
        grad_accum=1,
        lr=2e-4,
        max_seq_len=128,
        num_workers=0 # Pas de workers pour simplifier le débogage.
    )
    trainer = Qwen3Trainer(config)

    # Exécute l'entraînement.
    logger.info("Lancement de l'entraînement LoRA sur CPU...")
    try:
        trainer.train(dataset_path)
    except Exception as e:
        pytest.fail(f"L'entraînement LoRA a échoué : {e}")

    # Vérifie que le répertoire de sortie du modèle entraîné existe.
    output_model_path = Path(config.output_dir)
    assert output_model_path.exists(), "Le répertoire du modèle entraîné devrait exister."
    assert output_model_path.is_dir(), "Le chemin de sortie devrait être un répertoire."

    # Optionnel : Vérifier la présence de fichiers de modèle (ex: adapter_model.bin, adapter_config.json).
    # assert any(output_model_path.glob("*.bin")), "Le répertoire du modèle devrait contenir des fichiers binaires."
    # assert any(output_model_path.glob("*.json")), "Le répertoire du modèle devrait contenir des fichiers de configuration."

    logger.info("Test d'entraînement LoRA sur CPU terminé avec succès.")
