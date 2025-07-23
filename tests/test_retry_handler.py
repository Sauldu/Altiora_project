# tests/test_retry_handler.py
import pytest
import asyncio
from src.utils.retry_handler import RetryHandler


@pytest.mark.asyncio
async def test_retry_success():
    """Test que le retry fonctionne après échec"""
    call_count = 0

    @RetryHandler.with_retry(max_attempts=3)
    async def failing_function():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ValueError("Simulated failure")
        return "success"

    result = await failing_function()
    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_exhaustion():
    """Test que le retry s'arrête après max tentatives"""
    call_count = 0

    @RetryHandler.with_retry(max_attempts=2)
    async def always_failing():
        nonlocal call_count
        call_count += 1
        raise ValueError("Always fails")

    with pytest.raises(ValueError):
        await always_failing()
    assert call_count == 2
