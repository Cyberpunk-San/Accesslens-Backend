import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.wcag_engine import WCAGEngine
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

@pytest.mark.asyncio
async def test_wcag_engine_recovers_from_axe_timeout():
    """Verify WCAGEngine doesn't bring down the orchestrator if axe-core times out."""
    engine = WCAGEngine()
    
    # Mock page and force axe to timeout by sleeping longer than the engine's 30s timeout,
    # or simply raising asyncio.TimeoutError directly from the mock
    mock_page = AsyncMock()
    
    with patch.object(engine.axe, 'run', side_effect=asyncio.TimeoutError("Axe took too long")):
        issues = await engine.analyze({"page": mock_page}, request=None)
        
        # Should gracefully return an empty list instead of crashing
        assert isinstance(issues, list)
        assert len(issues) == 0

@pytest.mark.asyncio
async def test_wcag_engine_recovers_from_axe_exception():
    """Verify WCAGEngine doesn't crash on standard axe core execution failures."""
    engine = WCAGEngine()
    mock_page = AsyncMock()
    
    with patch.object(engine.axe, 'run', side_effect=Exception("Failed to inject axe")):
        issues = await engine.analyze({"page": mock_page}, request=None)
        
        assert isinstance(issues, list)
        assert len(issues) == 0
