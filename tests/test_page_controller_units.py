import pytest
pytestmark = pytest.mark.unit

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from app.core.page_controller import PageController

@pytest.fixture
def controller():
    return PageController()

@pytest.mark.asyncio
async def test_validate_url_cases(controller):
    # Safe URLs
    assert controller._is_safe_url("https://google.com") is True
    assert controller._is_safe_url("http://example.org/path?q=1") is True
    
    # Unsafe URLs (SSRF)
    assert controller._is_safe_url("http://localhost") is False
    assert controller._is_safe_url("http://127.0.0.1") is False
    assert controller._is_safe_url("http://169.254.169.254/latest/meta-data/") is False # AWS Metadata
    assert controller._is_safe_url("http://192.168.1.1") is False # Private IP
    assert controller._is_safe_url("file:///etc/passwd") is False # Wrong scheme
    assert controller._is_safe_url("ftp://example.com") is False

@pytest.mark.asyncio
async def test_navigate_and_extract_success(controller):
    mock_page = AsyncMock()
    mock_page.on = MagicMock()
    mock_page.goto.return_value = MagicMock(ok=True, status=200)
    mock_page.screenshot.return_value = b"fake_screenshot"
    
    with patch("app.core.page_controller.browser_manager") as mock_bm:
        mock_bm.get_page = AsyncMock(return_value=mock_page)
        
        # Mock tree extractor
        mock_tree = MagicMock() # Sync mock since we call sync methods on it
        mock_tree.extract = AsyncMock(return_value={"tree": "data"})
        mock_tree._get_timestamp.return_value = "2026-01-01T00:00:00Z"
        controller._tree_extractor = mock_tree
        
        # Mock CDP for metrics
        mock_client = AsyncMock()
        mock_client.send.return_value = {"metrics": [{"name": "m1", "value": 10}]}
        mock_page.context.new_cdp_session.return_value = mock_client
        mock_page.evaluate.return_value = {"timing": "data"}
        
        result = await controller.navigate_and_extract("https://safe-site.com")
        
        assert "tree" in result
        assert result["screenshot"] is not None
        assert result["metrics"]["metrics"]["m1"] == 10
        mock_bm.get_page.assert_called_once()
        mock_page.goto.assert_called_once()

@pytest.mark.asyncio
async def test_navigate_and_extract_unsafe_url(controller):
    with pytest.raises(ValueError, match="unsafe"):
        await controller.navigate_and_extract("http://localhost")

@pytest.mark.asyncio
async def test_navigate_retry_logic(controller):
    mock_page = AsyncMock()
    # Fail twice with Timeout, then succeed
    mock_page.goto.side_effect = [
        PlaywrightTimeoutError("Timeout 1"),
        PlaywrightTimeoutError("Timeout 2"),
        MagicMock(ok=True)
    ]
    
    with patch("app.core.page_controller.browser_manager") as mock_bm:
        mock_bm.get_page.return_value = mock_page
        # Speed up sleep
        with patch("asyncio.sleep", AsyncMock()):
            await controller._navigate(mock_page, "https://site.com", {"timeout": 1000})
            
    assert mock_page.goto.call_count == 3

@pytest.mark.asyncio
async def test_navigate_max_retries_exceeded(controller):
    mock_page = AsyncMock()
    mock_page.goto.side_effect = PlaywrightTimeoutError("Always timeout")
    
    with patch("asyncio.sleep", AsyncMock()):
        with pytest.raises(PlaywrightTimeoutError):
            await controller._navigate(mock_page, "https://site.com", {"timeout": 1000})
            
    assert mock_page.goto.call_count == 3

@pytest.mark.asyncio
async def test_highlight_element(controller):
    mock_page = AsyncMock()
    controller._current_page = mock_page
    
    # Success
    mock_page.evaluate.return_value = None
    assert await controller.highlight_element("#selector") is True
    
    # Failure
    mock_page.evaluate.side_effect = Exception("Eval failed")
    assert await controller.highlight_element("#bad") is False
