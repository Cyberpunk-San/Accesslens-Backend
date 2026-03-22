import pytest
from app.engines.contrast_engine import ContrastEngine
from app.models.schemas import AuditRequest, IssueSeverity
pytestmark = [pytest.mark.browser, pytest.mark.high_coverage]

@pytest.fixture
def contrast_engine():
    return ContrastEngine()

@pytest.mark.asyncio
async def test_contrast_low_opacity_text(contrast_engine, page):
    await page.set_content("""
        <html>
        <body style="background: white">
            <p id="pale" style="color: black; opacity: 0.2; font-size: 16px;">This is too pale</p>
        </body>
        </html>
    """)
    request = AuditRequest(url="about:blank")
    issues = await contrast_engine.analyze({"page": page}, request)
    
    contrast_issues = [i for i in issues if i.issue_type == "low_contrast_text"]
    assert len(contrast_issues) >= 1
    assert any("#pale" in i.location.selector for i in contrast_issues)

@pytest.mark.asyncio
async def test_contrast_semi_transparent_overlay(contrast_engine, page):
    await page.set_content("""
        <html>
        <body style="background: white">
            <div style="background: rgba(0,0,0,0.1); padding: 20px;">
                <p id="overlay-text" style="color: white">Hard to read</p>
            </div>
        </body>
        </html>
    """)
    request = AuditRequest(url="about:blank")
    issues = await contrast_engine.analyze({"page": page}, request)
    
    contrast_issues = [i for i in issues if i.issue_type == "low_contrast_text"]
    assert len(contrast_issues) >= 1
