import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.engines.contrast_engine import ContrastEngine
from app.models.schemas import AuditRequest, ElementLocation, EvidenceData, UnifiedIssue

pytestmark = pytest.mark.unit

@pytest.fixture
def contrast_engine():
    return ContrastEngine()

@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.evaluate = AsyncMock()
    return page

@pytest.mark.asyncio
async def test_contrast_analyze_success(contrast_engine, mock_page):
    request = AuditRequest(url="https://test.com")
    
    # Mock text elements
    text_el = {
        "selector": "h1",
        "tag": "h1",
        "text": "Hello",
        "color": "rgb(200, 200, 200)", # light gray
        "backgroundColor": "rgb(255, 255, 255)", # white (low contrast)
        "fontSize": 12,
        "isLargeText": False,
        "opacity": 1.0
    }
    
    # Mock UI elements
    ui_el = {
        "selector": "button",
        "tag": "button",
        "text": "Click me",
        "color": "rgb(0, 0, 0)",
        "backgroundColor": "rgb(200, 200, 200)", # gray on white bg
        "opacity": 1.0
    }
    
    # Mock evaluate calls
    def mock_evaluate(script, *args):
        if "elements.push({" in script and "isLargeText" in script:
            return [text_el]
        if "elements.push({" in script and "isInteractive" in script:
            return [ui_el]
        if "simulates mouse hover" in script or "new MouseEvent" in script:
            return None
        if "const elements = document.querySelectorAll" in script:
            return [] # No hover interactive elements
        if "(selector) => {" in script: # get_surrounding_background
            return "rgb(255, 255, 255)"
        return []
        
    mock_page.evaluate.side_effect = mock_evaluate
    
    issues = await contrast_engine.analyze({"page": mock_page}, request)
    
    assert len(issues) > 0
    assert any(i.issue_type == "low_contrast_text" for i in issues)
    assert any(i.issue_type == "low_contrast_ui" for i in issues)
    
    # Grouping test implicit since it's called at end of analyze
    assert hasattr(contrast_engine, "_last_patterns")

@pytest.mark.asyncio
async def test_contrast_analyze_failure(contrast_engine, mock_page):
    request = AuditRequest(url="https://test.com")
    mock_page.evaluate.side_effect = Exception("Page crashed")
    issues = await contrast_engine.analyze({"page": mock_page}, request)
    assert issues == []

@pytest.mark.asyncio
async def test_contrast_text_transparent_bg_fallback(contrast_engine, mock_page):
    request = AuditRequest(url="https://test.com")
    
    text_el = {
        "selector": "p",
        "tag": "p",
        "text": "Invisible text",
        "color": "rgba(255, 255, 255, 1)", # white text
        "backgroundColor": "transparent", # transparent bg
        "fontSize": 12,
        "isLargeText": False,
        "opacity": 1.0
    }
    
    def mock_evaluate(script, *args):
        if "isLargeText" in script:
            return [text_el]
        if "isInteractive" in script:
            return []
        if "(selector) => {" in script:
             # Surrounding bg is white
            return "rgb(255, 255, 255)"
        return []
        
    mock_page.evaluate.side_effect = mock_evaluate
    issues = await contrast_engine.analyze({"page": mock_page}, request)
    
    # Should catch low contrast (white text on white surrounding bg)
    assert any(i.issue_type == "low_contrast_text" for i in issues)

@pytest.mark.asyncio
async def test_contrast_interactive_states(contrast_engine, mock_page):
    request = AuditRequest(url="https://test.com")
    def mock_evaluate(script, *args):
        if "isLargeText" in script: return []
        if "isInteractive" in script: return []
        if "new MouseEvent" in script:
            # Hover style
            return {"color": "white", "backgroundColor": "white"}
        if "document.querySelectorAll('a, button" in script:
            return [{"selector": "a", "tag": "a", "normalColor": "black", "normalBg": "white"}]
        return None
    
    mock_page.evaluate.side_effect = mock_evaluate
    issues = await contrast_engine.analyze({"page": mock_page}, request)
    assert any(i.issue_type == "low_contrast_hover" for i in issues)

def test_suggest_color_fix(contrast_engine):
    from app.core.color_utils import RGBColor
    
    # White background, light gray fg
    fg = RGBColor(200, 200, 200)
    bg = RGBColor(255, 255, 255)
    
    suggestion = contrast_engine._suggest_color_fix(fg, bg, 4.5, 1.2)
    assert "Make text darker or background lighter" in suggestion
    
    # Needs tiny adjustment
    suggestion2 = contrast_engine._suggest_color_fix(fg, bg, 4.5, 4.0)
    assert "Adjust colors slightly" in suggestion2

def test_adjust_luminance(contrast_engine):
    from app.core.color_utils import RGBColor
    
    fg = RGBColor(150, 150, 150)
    bg = RGBColor(255, 255, 255)
    
    new_fg = contrast_engine._adjust_luminance(fg, bg, 21.0)
    assert new_fg.r < 150 # Should get much darker

def test_group_contrast_patterns(contrast_engine):
    from app.models.schemas import IssueSeverity, ConfidenceLevel, IssueSource
    issue1 = UnifiedIssue(
        title="Test", description="test", issue_type="low_contrast",
        severity=IssueSeverity.SERIOUS, confidence=ConfidenceLevel.HIGH, confidence_score=95.0, source=IssueSource.HEURISTIC,
        wcag_criteria=[],
        location=ElementLocation(selector="body", html=""),
        evidence=EvidenceData(computed_values={"foreground": "black", "background": "white", "ratio": 2.0}),
        engine_name="contrast", engine_version="1.0"
    )
    issue2 = UnifiedIssue(
        title="Test 2", description="test", issue_type="low_contrast",
        severity=IssueSeverity.SERIOUS, confidence=ConfidenceLevel.HIGH, confidence_score=95.0, source=IssueSource.HEURISTIC,
        wcag_criteria=[],
        location=ElementLocation(selector="body", html=""),
        evidence=EvidenceData(computed_values={"foreground": "black", "background": "white", "ratio": 2.0}),
        engine_name="contrast", engine_version="1.0"
    )
    
    groups = contrast_engine._group_contrast_patterns([issue1, issue2])
    assert len(groups) == 1
    assert groups[0]["count"] == 2
    assert groups[0]["foreground"] == "black"
