import pytest
import asyncio
from app.core.browser_manager import BrowserManager
pytestmark = pytest.mark.browser
from playwright.async_api import Page
import time
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_browser_manager_singleton():
    """Verify BrowserManager is a singleton."""
    bm1 = BrowserManager()
    bm2 = BrowserManager()
    assert bm1 is bm2

@pytest.mark.asyncio
async def test_browser_manager_max_concurrent_pages():
    """Verify max concurrent pages timeout logic.
    
    In testing mode get_page() uses max(_max_concurrent_pages, 10) as the effective
    cap, so we simulate pool exhaustion by directly setting _active_pages to the
    effective limit rather than fighting the dynamic override.
    """
    bm = BrowserManager()
    await bm.initialize(headless=True)

    original_active = bm._active_pages
    # In testing mode the effective max is max(_max_concurrent_pages, 10) == 10
    effective_max = max(bm._max_concurrent_pages, 10)

    try:
        # Fill the pool artificially so the next get_page() must wait
        bm._active_pages = effective_max

        # Should timeout immediately because pool is "full"
        with pytest.raises(TimeoutError, match="Timeout acquiring browser page"):
            await bm.get_page(timeout=1.0)

    finally:
        # Always hard-reset to 0 — singleton state can seep in from other tests
        bm._active_pages = 0

@pytest.mark.asyncio
async def test_browser_context_manager():
    """Verify the async context manager automatically releases the page."""
    bm = BrowserManager()
    await bm.initialize(headless=True)

    # Hard-reset active count — singleton may carry state from the previous test
    bm._active_pages = 0
    initial_active = bm._active_pages  # always 0

    async with bm.page_session(timeout=5.0) as page:
        assert bm._active_pages == initial_active + 1
        assert isinstance(page, Page)

    assert bm._active_pages == initial_active

    # Clean up
    await bm.close()

@pytest.mark.asyncio
async def test_browser_manager_recovery():
    """Verify that get_page recovers from transition errors."""
    bm = BrowserManager()
    await bm.initialize(headless=True)
    
    # Simulate a corrupted context by mocking new_page to raise an error once
    with patch.object(bm._context, "new_page", side_effect=[
        Exception("BrowserContext.new_page: 'NoneType' object has no attribute 'send'"),
        AsyncMock(spec=Page)
    ]) as mock_new_page:
        page = await bm.get_page(timeout=5.0)
        assert page is not None
        # mock_new_page gets hit once, raises error, triggers full restart
        # full restart recreates context, so the second call to new_page
        # goes to the REAL context, not the mock.
        assert mock_new_page.call_count == 1
        await bm.release_page(page)

    await bm.close()
