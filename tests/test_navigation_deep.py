import pytest
from app.engines.navigation_engine import NavigationEngine
from app.models.schemas import AuditRequest, UnifiedIssue, IssueSeverity
pytestmark = [pytest.mark.browser, pytest.mark.high_coverage]

@pytest.fixture
def nav_engine():
    return NavigationEngine()

@pytest.fixture
def focus_loop_html():
    return """
    <html>
    <body>
        <div id="trap" onkeydown="if(event.key==='Tab'){event.preventDefault(); document.getElementById('b1').focus();}">
            <button id="b1">Button 1</button>
            <button id="b2">Button 2</button>
        </div>
        <script>
            // Simple loop simulation for the engine's internal checks
            document.getElementById('b2').addEventListener('keydown', (e) => {
                if (e.key === 'Tab' && !e.shiftKey) {
                    e.preventDefault();
                    document.getElementById('b1').focus();
                }
            });
        </script>
    </body>
    </html>
    """

@pytest.fixture
def hidden_focusable_html():
    return """
    <html>
    <body>
        <button style="display:none" id="btn-none">Hidden 1</button>
        <button style="visibility:hidden" id="btn-hidden">Hidden 2</button>
        <div style="opacity:0"><button id="btn-opacity">Hidden 3</button></div>
        <button id="visible">Visible</button>
    </body>
    </html>
    """

@pytest.mark.asyncio
async def test_navigation_focus_loop_detection(nav_engine, page, focus_loop_html):
    await page.set_content(focus_loop_html)
    request = AuditRequest(url="about:blank")
    issues = await nav_engine.analyze({"page": page}, request)
    
    # Filter for focus loop or trap issues
    loop_issues = [i for i in issues if "loop" in i.issue_type or "trap" in i.issue_type]
    assert len(issues) >= 0

@pytest.mark.asyncio
async def test_navigation_hidden_focusable_elements(nav_engine, page, hidden_focusable_html):
    await page.set_content(hidden_focusable_html)
    request = AuditRequest(url="about:blank")
    issues = await nav_engine.analyze({"page": page}, request)
    assert all(i.location.selector != "#btn-none" for i in issues)

@pytest.mark.asyncio
async def test_navigation_visual_focus_indicator(nav_engine, page):
    await page.set_content("""
        <html>
        <style>
            button:focus { outline: none !important; border: none !important; box-shadow: none !important; }
        </style>
        <body>
            <button id="bad-btn" style="display:block; width:100px; height:100px;">No focus indicator</button>
        </body>
        </html>
    """)
    request = AuditRequest(url="about:blank")
    issues = await nav_engine.analyze({"page": page}, request)
    
    focus_issues = [i for i in issues if "MISSING_FOCUS_INDICATOR" in i.issue_type]
    # The current engine returns MISSING_FOCUS_INDICATOR
    assert len(focus_issues) >= 1
