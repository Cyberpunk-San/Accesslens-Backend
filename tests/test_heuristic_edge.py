import pytest
from unittest.mock import AsyncMock
from app.engines.heuristic_engine import HeuristicEngine
from app.models.schemas import AuditRequest

pytestmark = pytest.mark.unit

@pytest.fixture
def heuristic_engine():
    return HeuristicEngine()

@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.evaluate = AsyncMock()
    return page

@pytest.mark.asyncio
async def test_heuristic_analyze_success(heuristic_engine, mock_page):
    request = AuditRequest(url="https://test.com")
    
    def mock_evaluate(script, *args):
        if "meta[name=\"generator\"]" in script:
            return ["WordPress"]
        if "GENERIC =" in script or "click here" in script:
            return [{'type': 'vague_link', 'text': 'click here', 'count': 2, 'selector': 'a', 'html': '<a>'}]
        if "rect.width < 44 || rect.height < 44" in script:
            return [{'selector': 'btn', 'width': 30, 'height': 30, 'html': '<button>'}]
        if "video[autoplay]" in script:
            return [{'type': 'autoplay_video', 'selector': 'video', 'html': '<video>'}]
        if "style.overflow === 'hidden'" in script:
            return [{'selector': 'div', 'html': '<div>'}]
        if "meta[http-equiv=\"refresh\"]" in script:
            return [{'selector': 'meta', 'html': '<meta>'}]
        if "dist < 40" in script:
            return [{'selector': 'btn', 'count': 6, 'html': '<button>'}]
        if "a[title]" in script:
            return [{'selector': 'a', 'text': 'Read', 'html': '<a>'}]
        if "countSyllables" in script:
            return {'fkScore': 25, 'avgWordsPerSentence': 30, 'avgSyllablesPerWord': 2.5, 'wordCount': 100}
        if "nodeCount:" in script:
            # for false perfection, but won't trigger if issues > 2
            return {'nodeCount': 900, 'scrollHeight': 5000, 'textLength': 2500}
        return []
        
    mock_page.evaluate.side_effect = mock_evaluate
    
    issues = await heuristic_engine.analyze({"page": mock_page}, request)
    assert len(issues) > 0
    # ensure it hit reading complexity
    assert any(i.issue_type == "COGNITIVE_COMPLEXITY" for i in issues)

@pytest.mark.asyncio
async def test_heuristic_analyze_failure(heuristic_engine, mock_page):
    request = AuditRequest(url="https://test.com")
    mock_page.evaluate.side_effect = Exception("Evaluate Crash")
    issues = await heuristic_engine.analyze({"page": mock_page}, request)
    # All internal methods catch the exception and return []
    assert issues == []

@pytest.mark.asyncio
async def test_false_perfection_success(heuristic_engine, mock_page):
    request = AuditRequest(url="https://test.com")
    # Ensure no other issues are returned so integrity check triggers (requires issues <= 2)
    def mock_evaluate_integrity(script, *args):
        if "scrollHeight" in script:
            return {'nodeCount': 900, 'scrollHeight': 5000, 'textLength': 2500}
        return []
    mock_page.evaluate.side_effect = mock_evaluate_integrity
    issues = await heuristic_engine.analyze({"page": mock_page}, request)
    assert any(i.issue_type == "AUDIT_INTEGRITY" for i in issues)

@pytest.mark.asyncio
async def test_reading_complexity_pass_and_moderate(heuristic_engine, mock_page):
    request = AuditRequest(url="https://test.com")
    
    # Test fkScore >= 60 (Pass)
    def mock_evaluate_pass(script, *args):
        if "countSyllables" in script:
            return {'fkScore': 65, 'avgWordsPerSentence': 10, 'avgSyllablesPerWord': 1.5, 'wordCount': 100}
        return []
    mock_page.evaluate.side_effect = mock_evaluate_pass
    issues_pass = await heuristic_engine._check_reading_complexity(mock_page)
    assert len(issues_pass) == 0
    
    # Test fkScore < 60 but >= 30 (Moderate difficulty -> LOW confidence 65.0)
    def mock_evaluate_mod(script, *args):
        if "countSyllables" in script:
            return {'fkScore': 45, 'avgWordsPerSentence': 20, 'avgSyllablesPerWord': 2.0, 'wordCount': 100}
        return []
    mock_page.evaluate.side_effect = mock_evaluate_mod
    issues_mod = await heuristic_engine._check_reading_complexity(mock_page)
    assert len(issues_mod) == 1
    assert issues_mod[0].severity.value == "minor"
    assert issues_mod[0].confidence.value == "low"

@pytest.mark.asyncio
async def test_validate_config(heuristic_engine):
    assert await heuristic_engine.validate_config()
