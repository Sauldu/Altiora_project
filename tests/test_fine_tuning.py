import pytest
from pathlib import Path
from data.training.src.train_qwen3_thinkpad import Qwen3Trainer


@pytest.mark.slow
async def test_lora_training_cpu():
    """Test LoRA training on CPU with memory constraints"""
    trainer = Qwen3Trainer()

    # Create minimal dataset
    test_data = [
        {"instruction": "Test", "output": "Response"}
    ]

    # Configure for minimal memory
    trainer.config.per_device_train_batch_size = 1
    trainer.config.gradient_accumulation_steps = 2
    trainer.config.num_train_epochs = 1

    # Run training
    metrics = await trainer.train(test_data)

    assert metrics["train_loss"] < 10.0
    assert Path(trainer.config.output_dir).exists()