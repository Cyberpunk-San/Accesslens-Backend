import asyncio
import logging
import time
from typing import Optional, Dict, Any, List, AsyncGenerator
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from contextlib import asynccontextmanager

class BrowserManager:
    """
    Concurrent-safe singleton manager for Playwright browser and context.
    Uses an Event-based synchronization pattern to handle restarts safely.
    """
    _instance = None
    _playwright = None
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None
    _active_pages: int = 0
    
    # Synchronization
    _ready_event: asyncio.Event = None
    _restart_lock: asyncio.Lock = None
    _is_restarting: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._logger = logging.getLogger(__name__)
            cls._instance._ready_event = asyncio.Event()
            cls._instance._ready_event.set() # Initially ready
            cls._instance._restart_lock = asyncio.Lock()
            from .config import settings
            cls._instance._max_concurrent_pages = settings.browser_max_pages
        return cls._instance

    def __init__(self):
        pass

    async def initialize(self, headless: bool = True):
        """Standard initialization. If called during a restart, it waits."""
        await self._ready_event.wait()
        
        async with self._restart_lock:
            if self._browser and self._context:
                try:
                    # Quick check if context is still responding
                    test_page = await self._context.new_page()
                    await test_page.close()
                    return
                except Exception as e:
                    self._logger.warning(f"Browser unresponsive during check: {e}. Triggering soft restart.")
                    await self._soft_restart_unlocked(headless)
                    return

            await self._initialize_unlocked(headless)

    async def _initialize_unlocked(self, headless: bool):
        for attempt in range(2):
            try:
                if not self._playwright:
                    self._playwright = await async_playwright().start()
                
                if not self._browser:
                    self._browser = await self._playwright.chromium.launch(
                        headless=headless,
                        args=['--disable-dev-shm-usage', '--no-sandbox', '--disable-gpu']
                    )
                
                if not self._context:
                    self._context = await self._browser.new_context(
                        viewport={'width': 1280, 'height': 720},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    )
                self._logger.info("Browser environment initialized")
                self._ready_event.set()
                return
            except Exception as e:
                is_dead = "has no attribute 'send'" in str(e) or "Target closed" in str(e) or "Event loop is closed" in str(e)
                self._logger.error(f"Failed to initialize browser pool (attempt {attempt+1}): {e}")
                await self._close_unlocked(stop_playwright=True)
                if attempt == 0 and is_dead:
                    # Retry with a fundamentally fresh Playwright instance
                    continue
                raise

    async def get_page(self, timeout: float = 30.0) -> Page:
        """Acquires a page with safety for concurrent restarts."""
        from .config import settings
        max_pages = max(self._max_concurrent_pages, 10) if settings.testing else self._max_concurrent_pages
        
        start_time = time.time()
        # Wait for any active restart to finish
        await self._ready_event.wait()

        # Slot management
        while True:
            if self._active_pages < max_pages:
                self._active_pages += 1
                break
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Timeout acquiring browser page after {timeout} seconds")
            await asyncio.sleep(0.5)
            await self._ready_event.wait()

        try:
            for attempt in range(2):
                try:
                    if not self._browser or not self._context:
                        await self.initialize(headless=settings.browser_headless)
                    
                    # Ensure we aren't using a context that was just closed by another thread
                    await self._ready_event.wait()
                    
                    page = await self._context.new_page()
                    page.set_default_timeout(settings.browser_timeout)
                    return page
                except Exception as e:
                    self._logger.warning(f"Page acquisition attempt {attempt+1} failed: {e}")
                    if attempt == 0:
                        # Only ONE task should perform the restart
                        async with self._restart_lock:
                            if self._ready_event.is_set():
                                self._ready_event.clear()
                                is_playwright_dead = "has no attribute 'send'" in str(e) or "Target closed" in str(e) or "Event loop is closed" in str(e)
                                try:
                                    await self._soft_restart_unlocked(
                                        headless=settings.browser_headless,
                                        full_restart=is_playwright_dead
                                    )
                                except Exception as restart_err:
                                    self._logger.error(f"Restart failed: {restart_err}")
                    else:
                        raise
        except Exception:
            self._active_pages = max(0, self._active_pages - 1)
            raise

    async def _soft_restart_unlocked(self, headless: bool, full_restart: bool = False):
        """Closes browser/context but keeps Playwright alive to avoid killing other tasks, unless full_restart is requested."""
        self._logger.info(f"Performing {'full' if full_restart else 'soft'} browser restart...")
        try:
            if self._context:
                await self._context.close()
        except: pass
        try:
            if self._browser:
                await self._browser.close()
        except: pass
        
        if full_restart and self._playwright:
            try:
                await self._playwright.stop()
            except: pass
            self._playwright = None

        self._context = None
        self._browser = None
        # We DON'T reset _active_pages here as orphaned tasks are still returning their slots
        
        try:
            await self._initialize_unlocked(headless)
        finally:
            self._ready_event.set()

    async def release_page(self, page: Page):
        """Releases a page slot."""
        try:
            if not page.is_closed():
                await page.close()
        except Exception as e:
            self._logger.debug(f"Error closing page: {e}")
        finally:
            self._active_pages = max(0, self._active_pages - 1)

    @asynccontextmanager
    async def page_session(self, timeout: float = 30.0) -> AsyncGenerator[Page, None]:
        page = await self.get_page(timeout=timeout)
        try:
            yield page
        finally:
            await self.release_page(page)

    async def close(self):
        """Soft close."""
        async with self._restart_lock:
            await self._close_unlocked(stop_playwright=False)

    async def shutdown(self):
        """Full shutdown."""
        async with self._restart_lock:
            await self._close_unlocked(stop_playwright=True)

    async def _close_unlocked(self, stop_playwright: bool = False):
        self._ready_event.clear()
        try:
            if self._context:
                await self._context.close()
        except: pass
        try:
            if self._browser:
                await self._browser.close()
        except: pass
        
        if stop_playwright and self._playwright:
            try:
                await self._playwright.stop()
            except: pass
            self._playwright = None
            
        self._context = None
        self._browser = None
        self._active_pages = 0
        self._ready_event.set()

browser_manager = BrowserManager()