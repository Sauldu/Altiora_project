# src/training/train_qwen3_thinkpad.py
# !/usr/bin/env python3
"""
Qwen3-32B-Q4_K_M Fine-Tuning Trainer
CPU-optimisé pour 32 GB RAM (Intel i5 13ᵉⁿ)
"""

import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Qwen3Config:
    model_name: str = os.getenv("MODEL_NAME", "Qwen/Qwen3-32B-q4_K_M")
    output_dir: str = os.getenv("OUTPUT_DIR", "./models/qwen3-finetuned")
    lora_r: int = int(os.getenv("LORA_R", "16"))
    lora_alpha: int = int(os.getenv("LORA_ALPHA", "32"))
    lora_dropout: float = float(os.getenv("LORA_DROPOUT", "0.1"))
    epochs: int = int(os.getenv("EPOCHS", "3"))
    batch_size: int = int(os.getenv("BATCH_SIZE", "1"))
    grad_accum: int = int(os.getenv("GRAD_ACCUM", "32"))
    lr: float = float(os.getenv("LR", "2e-4"))
    max_seq_len: int = int(os.getenv("MAX_SEQ_LEN", "512"))
    num_workers: int = int(os.getenv("NUM_WORKERS", "4"))


class Qwen3Trainer:
    def __init__(self, cfg: Qwen3Config) -> None:
        self.config_path = Path("configs/training_config.json")
        self.config = self._load_config()
        self.cfg = cfg
        self.device = torch.device("cpu")
        self._check_ram()

    def _load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found at {self.config_path}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.config_path}")
            return {}

    @staticmethod
    def _check_ram() -> None:
        try:
            import psutil
            gb = psutil.virtual_memory().available / (1024 ** 3)
            if gb < 20:
                logger.warning("Available RAM %.1f GB – consider closing apps", gb)
        except ImportError:
            pass

    def _load_model_tokenizer(self) -> None:
        logger.info("Loading %s …", self.cfg.model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.cfg.model_name,
            trust_remote_code=True,
        )
        self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            self.cfg.model_name,
            device_map={"": self.device},
            torch_dtype=torch.float32,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )

        lora = LoraConfig(
            r=self.cfg.lora_r,
            lora_alpha=self.cfg.lora_alpha,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            lora_dropout=self.cfg.lora_dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        self.model = get_peft_model(self.model, lora)
        self.model.print_trainable_parameters()

        # Activation du gradient checkpointing
        self.model.gradient_checkpointing_enable()

        # Activation du mixed precision training
        self.model.half()

    def _load_dataset(self, path: Path) -> Dataset:
        ds = load_dataset(
            "json",
            data_files=str(path),
            streaming=True,
            cache_dir="./cache"
        )

        def fmt(sample):
            return {
                "text": (
                    f"<|im_start|>system\nTu es un expert en automatisation de tests.<|im_end|>\n"
                    f"<|im_start|>user\n{sample['instruction']}\n{sample.get('input', '')}<|im_end|>\n"
                    f"<|im_start|>assistant\n{sample['output']}<|im_end|>"
                )
            }

        ds = ds.map(fmt)
        return ds.map(
            lambda x: self.tokenizer(
                x["text"],
                padding="max_length",
                truncation=True,
                max_length=self.cfg.max_seq_len,
            ),
            batched=True,
            remove_columns=ds.column_names,
        )

    def train(self, dataset_path: Path) -> None:
        self._load_model_tokenizer()
        ds = self._load_dataset(dataset_path)

        args = TrainingArguments(
            output_dir=self.cfg.output_dir,
            num_train_epochs=self.cfg.epochs,
            per_device_train_batch_size=self.cfg.batch_size,
            gradient_accumulation_steps=self.cfg.grad_accum,
            learning_rate=self.cfg.lr,
            optim="adamw_torch",
            logging_steps=10,
            save_steps=100,
            save_total_limit=3,
            report_to="tensorboard",
            dataloader_num_workers=self.cfg.num_workers,
            remove_unused_columns=False,
            fp16=True,  # Mixed precision
            bf16=False,
            tf32=False,
            dataloader_pin_memory=False,
        )

        trainer = Trainer(
            model=self.model,
            args=args,
            train_dataset=ds,
            data_collator=DataCollatorForLanguageModeling(
                tokenizer=self.tokenizer, mlm=False
            ),
            tokenizer=self.tokenizer,
        )

        logger.info("Starting training …")
        trainer.train()
        trainer.save_model()
        logger.info("Training complete → %s", self.cfg.output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path, help="JSONL dataset")
    parser.add_argument("--output", type=Path, default=Path("./models/qwen3-finetuned"))
    args = parser.parse_args()

    config = Qwen3Config(output_dir=str(args.output))
    trainer = Qwen3Trainer(config)
    trainer.train(args.dataset)
