# tests/integration/test_services_integration.py
"""
Tests d'intégration entre les services microservices
"""

import pytest
import asyncio
import aiohttp
from pathlib import Path


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ocr_to_qwen3_flow():
    """Test OCR → Qwen3 → StarCoder2 → Playwright."""

    # 1. OCR extraction
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Test de connexion avec email et mot de passe")
        sfd_path = f.name

    try:
        # 2. Mock OCR (ou vrai service)
        ocr_result = {"text": "Test login page with email and password fields"}

        # 3. Qwen3 analysis
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "qwen3-sfd-analyzer",
                        "prompt": f"Analyze: {ocr_result['text']}",
                        "format": "json"
                    }
            ) as resp:
                qwen3_result = await resp.json()

        # 4. StarCoder2 generation
        async with session.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "starcoder2-playwright",
                    "prompt": f"Generate test for: {qwen3_result['response']}",
                    "format": "json"
                }
        ) as resp:
            starcoder2_result = await resp.json()

        assert "test_" in starcoder2_result.get("response", "")

    finally:
        Path(sfd_path).unlink()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_excel_alm_integration():
    """Test Excel → ALM workflow."""

    test_data = [
        {
            "id": "CU01_SB01_CP001_login_success",
            "description": "Test connexion réussie",
            "type": "CP",
            "priority": "HIGH"
        }
    ]

    # 1. Excel generation
    async with aiohttp.ClientSession() as session:
        async with session.post(
                "http://localhost:8003/create-test-matrix",
                json={"filename": "integration_test.xlsx", "test_cases": test_data}
        ) as resp:
            excel_response = await resp.read()
            assert len(excel_response) > 0

    # 2. ALM import
    async with session.post(
            "http://localhost:8002/work-items",
            json={
                "title": "Test case import",
                "description": "Automated test cases from Excel",
                "item_type": "Test"
            }
    ) as resp:
        alm_result = await resp.json()
        assert alm_result["success"] is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_playwright_execution():
    """Test d'exécution réelle de tests Playwright."""

    test_code = '''
import pytest
from playwright.async_api import Page, expect

@pytest.mark.asyncio
async def test_example(page: Page):
    await page.goto("https://httpbin.org/status/200")
    await expect(page).to_have_title(/.*/)
'''

    payload = {
        "tests": [{"code": test_code, "test_name": "test_httpbin"}],
        "config": {
            "browser": "chromium",
            "headless": True,
            "timeout": 30000
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
                "http://localhost:8004/execute",
                json=payload
        ) as resp:
            result = await resp.json()
            assert result["status"] == "completed"