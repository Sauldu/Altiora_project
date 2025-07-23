#!/usr/bin/env python3
"""
Altiora One-Click Setup
- Python ≥ 3.8
- Docker (recommended)
- Redis
- Ollama models
"""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

from configs.config_module import get_settings


class AltioraSetup:
    """Idempotent installer for Altiora."""

    def __init__(self, base_dir: Path = Path.cwd()) -> None:
        self.base_dir = base_dir
        self.venv_path = base_dir / ".venv"
        self.python_min = (3, 8)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.successes: List[str] = []
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # Public flow
    # ------------------------------------------------------------------
    def run(self, *, skip_services: bool = False, dev_mode: bool = False) -> None:
        print("🚀 Altiora installer")
        print("=" * 60)

        self.check_python_version()
        self.check_system_requirements()
        self.setup_virtual_environment()
        self.install_dependencies(dev_mode)
        self.setup_environment()
        self.create_directories()
        if not skip_services:
            self.setup_ollama_models()
            self.check_services()
        self.init_database()
        self.print_summary()

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------
    def check_python_version(self) -> None:
        if sys.version_info < self.python_min:
            self.errors.append(
                f"Python ≥ {'.'.join(map(str, self.python_min))} required"
            )
            sys.exit(1)
        self.successes.append(f"Python {'.'.join(map(str, sys.version_info[:2]))} ✓")

    def check_system_requirements(self) -> None:
        tools = [("Git", "git"), ("Docker", "docker")]
        for name, cmd in tools:
            if shutil.which(cmd):
                self.successes.append(f"{name} ✓")
            else:
                self.warnings.append(f"{name} not found")

    # ------------------------------------------------------------------
    # Virtual env
    # ------------------------------------------------------------------
    def setup_virtual_environment(self) -> None:
        import venv  # stdlib – no extra install needed

        if not self.venv_path.exists():
            venv.create(self.venv_path, with_pip=True)
            self.successes.append("Virtual environment created")
        else:
            self.successes.append("Virtual environment exists")

        self._write_activation_script()

    def _write_activation_script(self) -> None:
        if platform.system() == "Windows":
            script = self.base_dir / "activate.bat"
            script.write_text(
                f"@echo off\ncall {self.venv_path}\\Scripts\\activate.bat\necho Activated\n"
            )
        else:
            script = self.base_dir / "activate.sh"
            script.write_text(
                f'#!/bin/bash\nsource {self.venv_path}/bin/activate\necho Activated\n'
            )
            script.chmod(0o755)

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------
    def install_dependencies(self, dev: bool) -> None:
        pip = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        if dev:
            pip.extend(["-r", "requirements-dev.txt"])

        subprocess.run(pip, check=True)
        self.successes.append("Dependencies installed")

        if "playwright" in Path("requirements.txt").read_text():
            subprocess.run(["playwright", "install", "chromium"], check=True)

    # ------------------------------------------------------------------
    # Environment & directories
    # ------------------------------------------------------------------
    def setup_environment(self) -> None:
        env_src, env_dst = Path(".env.example"), Path(".env")
        if env_src.exists() and not env_dst.exists():
            env_dst.write_text(env_src.read_text())
            self._inject_jwt_secret(env_dst)

    @staticmethod
    def _inject_jwt_secret(env_file: Path) -> None:
        import secrets

        text = env_file.read_text()
        if "your-secret-key-here" in text:
            key = secrets.token_urlsafe(32)
            env_file.write_text(text.replace("your-secret-key-here", key))

    def create_directories(self) -> None:
        dirs = [
                   self.settings.data_dir / d
                   for d in ["input", "processed", "cache", "matrices"]
               ] + [
                   self.settings.models_dir,
                   self.settings.logs_dir,
                   self.settings.reports_dir,
                   self.settings.temp_dir,
                   Path("workspace"),
                   Path("tests/generated"),
                   Path("screenshots"),
                   Path("videos"),
               ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        self.successes.append("Directories ready")

    # ------------------------------------------------------------------
    # Ollama & services
    # ------------------------------------------------------------------
    def setup_ollama_models(self) -> None:
        models = [m.base_model for m in self.settings.models.values()]
        for model in models:
            subprocess.run(["ollama", "pull", model], check=True)

    def check_services(self) -> None:
        services = [
            ("Redis", "redis-cli", ["ping"]),
            ("OCR", "curl", ["-s", "http://localhost:8001/health"]),
            ("ALM", "curl", ["-s", "http://localhost:8002/health"]),
            ("Excel", "curl", ["-s", "http://localhost:8003/health"]),
            ("Playwright", "curl", ["-s", "http://localhost:8004/health"]),
        ]
        for name, cmd, args in services:
            try:
                subprocess.run([cmd, *args], check=True, stdout=subprocess.DEVNULL)
                self.successes.append(f"{name} ✓")
            except Exception:
                self.warnings.append(f"{name} unreachable")

    def init_database(self) -> None:
        self.successes.append("No SQL DB configured (Redis only) ✓")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def print_summary(self) -> None:
        print("\n" + "=" * 60)
        print("📊 Summary")
        for label, items in (
                ("✅", self.successes),
                ("⚠️", self.warnings),
                ("❌", self.errors),
        ):
            if items:
                print(f"{label} {len(items)}")
                for item in items:
                    print(f"   • {item}")
        if self.errors:
            sys.exit(1)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Altiora installer")
    parser.add_argument("--skip-services", action="store_true")
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()

    if not Path("requirements.txt").exists():
        print("❌ Run from project root")
        sys.exit(1)

    AltioraSetup().run(skip_services=args.skip_services, dev_mode=args.dev)


if __name__ == "__main__":
    main()
