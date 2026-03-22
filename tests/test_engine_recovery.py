import pytest
import asyncio
from unittest.mock import MagicMock
from app.engines.navigation_engine import NavigationEngine
from app.engines.heuristic_engine import HeuristicEngine
from app.models.schemas import AuditRequest

pytestmark = [pytest.mark.browser, pytest.mark.high_coverage]

@pytest.fixture
def nav_engine():
    return NavigationEngine()

@pytest.fixture
def heuristic_engine():
    return HeuristicEngine()

@pytest.mark.asyncio
async def test_navigation_aria_owns_loop(nav_engine, page):
    # Create an aria-owns loop
    await page.set_content("""
        <html><body>
            <div id="parent1" aria-owns="child1">
                <div id="child1" aria-owns="parent1">LOOP</div>
            </div>
        </body></html>
    """)
    request = AuditRequest(url="about:blank")
    issues = await nav_engine.analyze({"page": page}, request)
    # The engine should not hang and should ideally detect the complex structure
    assert isinstance(issues, list)

@pytest.mark.asyncio
async def test_navigation_shadow_dom(nav_engine, page):
    # Create Shadow DOM with a button
    await page.evaluate("""
        () => {
            const host = document.createElement('div');
            host.id = 'shadow-host';
            document.body.appendChild(host);
            const shadow = host.attachShadow({mode: 'open'});
            shadow.innerHTML = '<button id="shadow-btn">Shadow Button</button>';
        }
    """)
    # Check if a standard selector fails but a deep script finds it
    btn_count = await page.evaluate("document.querySelectorAll('button').length")
    assert btn_count == 0 # Standard selector doesn't see shadow DOM
    
    request = AuditRequest(url="about:blank")
    issues = await nav_engine.analyze({"page": page}, request)
    # If the engine handles shadow DOM, it might find issues there or at least not crash
    assert isinstance(issues, list)

@pytest.mark.asyncio
async def test_heuristic_clutter_threshold_exact(heuristic_engine, page):
    # Threshold is > 5. Let's test with exactly 5 neighbors (6 total interactive elements)
    # 6 buttons in a 2x3 grid
    btns = "".join(['<button style="width:10px;height:10px;display:inline-block;">B</button>' for i in range(6)])
    await page.set_content(f"<html><body><div style='width:30px;'>{btns}</div></body></html>")
    
    request = AuditRequest(url="about:blank")
    issues = await heuristic_engine.analyze({"page": page}, request)
    # Should be 0 clutter issues if threshold is > 5 and neighbors == 5
    clutter = [i for i in issues if "density" in i.title.lower()]
    assert len(clutter) == 0

@pytest.mark.asyncio
async def test_heuristic_clutter_threshold_trigger(heuristic_engine, page):
    # 7 buttons in a tight grid (neighbors will be 6)
    btns = "".join(['<button style="width:10px;height:10px;display:inline-block;">B</button>' for i in range(7)])
    await page.set_content(f"<html><body><div style='width:30px;'>{btns}</div></body></html>")
    
    request = AuditRequest(url="about:blank")
    issues = await heuristic_engine.analyze({"page": page}, request)
    clutter = [i for i in issues if "density" in i.title.lower()]
    assert len(clutter) >= 1

@pytest.mark.asyncio
async def test_heuristic_complex_language_short(heuristic_engine, page):
    # Less than 100 words should be ignored
    short_text = "The cat sat on the mat. " * 10 
    await page.set_content(f"<html><body><p>{short_text}</p></body></html>")
    
    request = AuditRequest(url="about:blank")
    issues = await heuristic_engine.analyze({"page": page}, request)
    cognitive = [i for i in issues if i.issue_type == "COGNITIVE_COMPLEXITY"]
    assert len(cognitive) == 0
