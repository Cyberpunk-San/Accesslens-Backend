import pytest
pytestmark = pytest.mark.unit

from unittest.mock import MagicMock
from app.engines.ai_engine import AIEngine
from app.models.schemas import UnifiedIssue, IssueSeverity, ConfidenceLevel

@pytest.fixture
def engine():
    return AIEngine()

def test_parse_vision_results_basic(engine):
    mock_results = {
        "findings": [
            {"description": "Too much clutter", "severity": "serious", "confidence": 0.9},
            {"description": "Low contrast icon", "severity": "minor"}
        ]
    }
    issues = engine._parse_vision_results(mock_results, {})
    assert len(issues) == 2
    assert issues[0].severity == IssueSeverity.SERIOUS
    assert issues[1].severity == IssueSeverity.MINOR
    assert "vision_clutter" in issues[0].issue_type or "vision_unknown" in issues[0].issue_type

def test_parse_vision_results_malformed(engine):
    # Missing findings key
    issues = engine._parse_vision_results({}, {})
    assert issues == []

@pytest.mark.asyncio
async def test_analyze_alt_text_quality_vague(engine):
    # Mock accessibility tree structure
    acc_tree = {
        "structure": {
            "focusable_elements": [
                {"role": "link", "name": "click here"},
                {"role": "button", "name": "  "},
                {"role": "link", "name": "valid description"}
            ]
        }
    }
    issues = await engine._analyze_alt_text_quality(acc_tree)
    assert len(issues) == 2
    titles = [i.title for i in issues]
    assert "Empty button found" in titles
    assert "Vague link or button text" in titles

@pytest.mark.asyncio
async def test_analyze_layout_complexity(engine):
    dom_low = {"statistics": {"total_elements": 50}}
    dom_high = {"statistics": {"total_elements": 2000}} # High density
    
    issues_low = await engine._analyze_layout_complexity(dom_low)
    issues_high = await engine._analyze_layout_complexity(dom_high)
    
    assert len(issues_low) == 0
    assert len(issues_high) == 1
    assert issues_high[0].issue_type == "visual_clutter"

@pytest.mark.asyncio
async def test_analyze_interactive_patterns(engine):
    acc_tree_low = {"structure": {"focusable_elements": [{"role": "button"}] * 5}}
    acc_tree_high = {"structure": {"focusable_elements": [{"role": "button"}] * 100}} # High interactive count
    
    issues_low = await engine._analyze_interactive_patterns(acc_tree_low)
    issues_high = await engine._analyze_interactive_patterns(acc_tree_high)
    
    assert len(issues_low) == 0
    assert len(issues_high) == 1
    assert issues_high[0].issue_type == "focus_visibility_check"

def test_create_error_issues(engine):
    errs = engine._create_error_issues("Test error")
    assert len(errs) == 1
    assert errs[0].description == "Test error"
    assert "error" in errs[0].tags
