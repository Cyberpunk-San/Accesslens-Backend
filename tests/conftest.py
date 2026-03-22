import pytest
import asyncio
import sys
from unittest.mock import MagicMock
sys.modules["torch"] = MagicMock()
from typing import Generator, Dict, Any
from playwright.async_api import async_playwright, Browser, Page
from app.core.config import settings
from app.core.browser_manager import browser_manager
from app.utils.cache import cache_manager
from app.middleware.rate_limit import rate_limiter

# Removed deprecated session-scoped event_loop fixture

@pytest.fixture(scope="session", autouse=True)
def set_testing_mode():
    """Ensure testing mode is active for the entire session."""
    settings.testing = True
    yield

@pytest.fixture(scope="function", autouse=True)
async def cleanup_browser_manager():
    """Ensure the singleton is completely reset between tests so dead loops don't trigger warnings."""
    yield
    await browser_manager.shutdown()

@pytest.fixture(scope="function")
async def browser():

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()

@pytest.fixture
async def page(browser: Browser):

    page = await browser.new_page()
    yield page
    await page.close()

@pytest.fixture
def test_html() -> str:

    from . import SAMPLE_HTML
    return SAMPLE_HTML

@pytest.fixture
def inaccessible_html() -> str:

    from . import INACCESSIBLE_HTML
    return INACCESSIBLE_HTML

@pytest.fixture
def mock_audit_request() -> Dict[str, Any]:

    return {
        "url": "https://example.com",
        "engines": ["wcag_deterministic", "contrast_engine", "structural_engine"],
        "enable_ai": False,
        "depth": "quick",
        "viewport": {"width": 1280, "height": 720},
        "wait_for_network_idle": True
    }

@pytest.fixture
async def unit_env():
    """Lightweight test environment for unit tests."""
    settings.debug = True
    settings.testing = True
    # No app lifespan, no cache initialization
    yield

@pytest.fixture(autouse=False)
async def integration_env():
    """Full application environment for integration/browser tests."""
    from app.main import app, lifespan
    
    settings.debug = True
    settings.testing = True
    settings.log_level = "DEBUG"

    # Reset rate limiter
    rate_limiter.requests.clear()

    await cache_manager.initialize()
    await cache_manager.clear()

    async with lifespan(app):
        yield




@pytest.fixture
async def initialized_browser_manager():

    await browser_manager.initialize(headless=True)
    yield browser_manager
    await browser_manager.close()