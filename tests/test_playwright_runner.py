# tests/test_playwright_runner.py
import pytest
import asyncio
from pathlib import Path
from services.playwright.playwright_runner import prepare_test_files, generate_pytest_config


@pytest.fixture
def test_scenario():
    return {
        "code": "await page.goto('https://example.com')",
        "test_name": "test_navigation",
        "test_type": "e2e"
    }


@pytest.fixture
def temp_workspace(tmp_path):
    return tmp_path / "workspace"


def test_prepare_test_files(temp_workspace, test_scenario):
    """Test la préparation des fichiers de test."""
    temp_workspace.mkdir()

    test_files = asyncio.run(prepare_test_files([test_scenario], temp_workspace))

    assert len(test_files) == 1
    assert test_files[0].exists()
    assert test_files[0].suffix == ".py"
    assert "test_navigation" in test_files[0].name


def test_pytest_config_generation():
    """Test la génération de configuration pytest."""
    from services.playwright.playwright_runner import ExecutionConfig

    config = ExecutionConfig(
        browser="firefox",
        headed=True,
        parallel=True,
        workers=3
    )

    pytest_args = generate_pytest_config(config, Path("/test"))

    assert "--browser=firefox" in pytest_args
    assert "--headed" in pytest_args
    assert "-n" in pytest_args
    assert "3" in pytest_args