import pytest
pytestmark = pytest.mark.browser

import asyncio
from playwright.async_api import Page
from app.engines.structural_engine import StructuralEngine
from app.engines.heuristic_engine import HeuristicEngine
from app.engines.ai_engine import AIEngine
from app.engines.form_engine import FormEngine
from app.models.schemas import AuditRequest

@pytest.mark.asyncio
async def test_enhanced_structural_detection(page: Page):
    # Setup page with multiple issues
    content = """
    <html>
    <body>
        <a href="#nonexistent">Skip to content</a>
        <nav>
            <button aria-haspopup="true">Menu</button>
            <a href="test.pdf">Download Guide</a>
        </nav>
        <h1>Title</h1>
        <h3>Skipped Header</h3>
        <div aria-live="polite" role="status">Updating...</div>
    </body>
    </html>
    """
    await page.set_content(content)
    
    engine = StructuralEngine()
    request = AuditRequest(url="http://test.com")
    page_data = {"page": page}
    
    issues = await engine.analyze(page_data, request)
    
    # Verify Lang Attribute (Point 4)
    assert any(i.issue_type == "missing_lang" for i in issues)
    
    # Verify Skip Link (Point 14)
    assert any(i.issue_type == "invalid_skip_link" for i in issues)
    
    # Verify Heading Skip (Point 1)
    assert any(i.issue_type == "heading_skip" for i in issues)
    
    # Verify Dropdown (Point 13)
    assert any(i.issue_type == "missing_aria_expanded" for i in issues)
    
    # Verify Non-HTML (Point 15)
    assert any(i.issue_type == "non_html_link" for i in issues)

@pytest.mark.asyncio
async def test_enhanced_heuristic_detection(page: Page):
    content = """
    <html>
    <head><meta http-equiv="refresh" content="30"></head>
    <body style="width: 1000px;">
        <a href="#">Read more</a>
        <button style="width: 20px; height: 20px;">X</button>
        <video autoplay src="test.mp4"></video>
        <div style="height: 50px; overflow: hidden;">
            Long text that might get clipped when zoomed in... 
            Long text that might get clipped when zoomed in...
            Long text that might get clipped when zoomed in...
        </div>
    </body>
    </html>
    """
    await page.set_content(content)
    
    engine = HeuristicEngine()
    request = AuditRequest(url="http://test.com")
    page_data = {"page": page}
    
    issues = await engine.analyze(page_data, request)
    
    # Verify Vague Link (Point 3)
    assert any(i.issue_type == "VAGUE_LINK_TEXT" for i in issues)
    
    # Verify Touch Target (Point 6)
    assert any(i.issue_type == "TOUCH_TARGET_SIZE" for i in issues)
    
    # Verify Animation (Point 9)
    assert any(i.issue_type == "ANIMATION_CHECK" for i in issues)
    
    # Verify Zoom/Clipping (Point 11)
    assert any(i.issue_type == "ZOOM_CHECK" for i in issues)
    
    # Verify Timeout (Point 12)
    assert any(i.issue_type == "TIMEOUT_CHECK" for i in issues)

@pytest.mark.asyncio
async def test_enhanced_ai_detection(page: Page):
    content = """
    <html>
    <body>
        <img src="drdo.png" alt="DRDO">
        <img src="test.jpg">
    </body>
    </html>
    """
    await page.set_content(content)
    
    engine = AIEngine()
    # Mock AI services to avoid actual LLM calls in test
    engine._initialized = True 
    
    request = AuditRequest(url="http://test.com")
    page_data = {"page": page, "accessibility_tree": {}}
    
    issues = await engine.analyze(page_data, request)
    
    # Verify Alt Text Quality (Point 2)
    assert any(i.issue_type == "missing_alt" for i in issues)
    assert any(i.issue_type == "vague_alt_text" for i in issues)

@pytest.mark.asyncio
async def test_enhanced_form_detection(page: Page):
    content = """
    <html>
    <body>
        <form>
            <label for="name">Name</label>
            <input id="name" required>
            <div class="error">This field is required</div>
            
            <input id="email" aria-describedby="email-desc">
            <span id="email-desc">Enter your email</span>
        </form>
    </body>
    </html>
    """
    await page.set_content(content)
    
    engine = FormEngine()
    request = AuditRequest(url="http://test.com")
    page_data = {"page": page}
    
    issues = await engine.analyze(page_data, request)
    
    # Verify Missing Instruction (Point 8)
    assert any(i.issue_type == "MISSING_INSTRUCTION" for i in issues)
    
    # Verify Missing Error Link (Point 8)
    assert any(i.issue_type == "MISSING_ERROR_LINK" for i in issues)
