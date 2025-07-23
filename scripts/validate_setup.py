#!/usr/bin/env python3
"""
Comprehensive validation script for Altiora setup
"""
import sys
from pathlib import Path
import subprocess
import yaml


class SetupValidator:
    """Validate complete Altiora installation"""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_models(self):
        """Check Ollama models consistency"""
        # Check if models match configuration
        models_config = yaml.safe_load(
            Path("configs/models.yaml").read_text()
        )

        # Verify with Ollama
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True
        )

        installed_models = result.stdout

        for model_name, config in models_config["models"].items():
            if config["ollama_tag"] not in installed_models:
                self.errors.append(
                    f"Model {config['ollama_tag']} not installed"
                )

    def validate_dependencies(self):
        """Check all Python dependencies"""
        try:
            import torch
            import transformers
            import peft

            # Check versions
            if not torch.__version__.startswith("2.2"):
                self.warnings.append(
                    f"PyTorch version {torch.__version__} may cause issues"
                )

        except ImportError as e:
            self.errors.append(f"Missing dependency: {e}")

    def run(self):
        """Run all validations"""
        self.validate_models()
        self.validate_dependencies()

        # Print results
        if self.errors:
            print("❌ ERRORS FOUND:")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  - {warning}")

        return len(self.errors) == 0


if __name__ == "__main__":
    validator = SetupValidator()
    if not validator.run():
        sys.exit(1)