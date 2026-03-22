import pytest
import asyncio
from app.engines.heuristic_engine import HeuristicEngine
from app.models.schemas import AuditRequest
pytestmark = [pytest.mark.browser, pytest.mark.high_coverage]

@pytest.fixture
def heuristic_engine():
    return HeuristicEngine()

@pytest.mark.asyncio
async def test_heuristic_cluttered_ui(heuristic_engine, page):
    # 20 buttons in a tight grid
    btns = "".join([f'<button style="width:10px;height:10px;display:inline-block;">B</button>' for i in range(20)])
    await page.set_content(f"<html><body><div style='width:30px;'>{btns}</div></body></html>")
    await page.wait_for_selector("button")
    await asyncio.sleep(0.5)
    
    request = AuditRequest(url="about:blank")
    issues = await heuristic_engine.analyze({"page": page}, request)
    assert len(issues) >= 1, f"NO ISSUES RETURNED! LOGS: {issues}"
    clutter_issues = [i for i in issues if "density" in i.title.lower()]
    assert len(clutter_issues) >= 1, f"NO DENSITY ISSUES! GOT: {[i.title for i in issues]}"

@pytest.mark.asyncio
async def test_heuristic_complex_language(heuristic_engine, page):
    complex_text = "The obfuscation of transcendental existentialism in post-modernist epistemological paradigms necessitates an intersectional deconstruction of ontological presuppositions."
    full_text = (complex_text + " ") * 15 # > 100 words
    await page.set_content(f"<html><body><p>{full_text}</p></body></html>")
    
    request = AuditRequest(url="about:blank")
    issues = await heuristic_engine.analyze({"page": page}, request)
    reading_issues = [i for i in issues if i.issue_type == "COGNITIVE_COMPLEXITY"]
    assert len(reading_issues) >= 1
