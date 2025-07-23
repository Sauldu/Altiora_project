# tests/test_ocr_wrapper.py
import pytest
import asyncio
from pathlib import Path
from services.ocr.ocr_wrapper import extract_with_doctoplus, generate_cache_key


@pytest.mark.asyncio
async def test_ocr_cache_key_generation():
    """Test la génération de clés de cache."""
    request = type('Request', (), {
        'file_path': '/test/sample.pdf',
        'language': 'fra',
        'preprocess': True,
        'output_format': 'text'
    })

    cache_key = generate_cache_key(request)
    assert cache_key.startswith('ocr:')
    assert len(cache_key) == 39  # "ocr:" + 32 chars MD5


@pytest.mark.asyncio
async def test_mock_ocr_extraction():
    """Test l'extraction OCR en mode mock."""
    from services.ocr.ocr_wrapper import extract_mock

    class MockRequest:
        file_path = "test.pdf"
        language = "fra"
        preprocess = True

    result = await extract_mock(MockRequest())
    assert "mock" in result["text"].lower()
    assert result["confidence"] > 0
    assert "metadata" in result