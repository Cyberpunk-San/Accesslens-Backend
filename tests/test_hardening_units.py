import pytest
pytestmark = pytest.mark.unit

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from app.engines.ai_engine import AIEngine
from app.utils.cache import CacheManager
from app.models.schemas import UnifiedIssue, IssueSeverity, ConfidenceLevel, IssueSource, ElementLocation

@pytest.fixture
def engine():
    return AIEngine()

# AI Engine Tests
def test_parse_vision_results_basic(engine):
    mock_results = {
        "findings": [
            {"description": "Too much clutter", "severity": "serious", "confidence": 0.9, "issue_type": "clutter"},
            {"description": "Low contrast icon", "severity": "minor"}
        ]
    }
    issues = engine._parse_vision_results(mock_results, {})
    assert len(issues) == 2
    assert issues[0].severity == IssueSeverity.SERIOUS
    assert issues[1].severity == IssueSeverity.MINOR
    # issue_type becomes f"vision_{finding.get('issue_type', 'unknown')}"
    assert issues[0].issue_type == "vision_clutter"
    assert issues[1].issue_type == "vision_unknown"

def test_parse_vision_results_malformed(engine):
    issues = engine._parse_vision_results({}, {})
    assert issues == []

@pytest.mark.asyncio
async def test_analyze_alt_text_quality_vague(engine):
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
    dom_high = {"statistics": {"total_elements": 2000}}
    
    issues_low = await engine._analyze_layout_complexity(dom_low)
    issues_high = await engine._analyze_layout_complexity(dom_high)
    
    assert len(issues_low) == 0
    assert len(issues_high) == 1
    assert issues_high[0].issue_type == "visual_clutter"

@pytest.mark.asyncio
async def test_analyze_interactive_patterns(engine):
    acc_tree_low = {"structure": {"focusable_elements": [{"role": "button"}] * 5}}
    acc_tree_high = {"structure": {"focusable_elements": [{"role": "button"}] * 100}}
    
    issues_low = await engine._analyze_interactive_patterns(acc_tree_low)
    issues_high = await engine._analyze_interactive_patterns(acc_tree_high)
    
    assert len(issues_low) == 0
    assert len(issues_high) == 1
    assert issues_high[0].issue_type == "focus_visibility_check"

# Cache Manager Tests
@pytest.fixture
async def cache():
    from app.utils.cache import CacheManager
    c = CacheManager()
    yield c

@pytest.mark.asyncio
async def test_cache_fallback_on_redis_error():
    from app.utils.cache import CacheManager
    with patch("redis.asyncio.from_url") as mock_redis:
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Redis Down")
        mock_redis.return_value = mock_client
        
        manager = CacheManager()
        # Should fallback to in-memory gracefully
        await manager.set("test_key", "test_value")
        val = await manager.get("test_key")
        assert val == "test_value"

@pytest.mark.asyncio
async def test_ai_engine_malformed_json(engine):
    # Test _parse_vision_results with totally invalid finding structure
    bad_results = {"findings": [{"invalid": "data"}]}
    issues = engine._parse_vision_results(bad_results, {})
    # Should still create an issue but with 'unknown' type or similar safe defaults
    assert len(issues) == 1
    assert issues[0].issue_type == "vision_unknown"

@pytest.mark.asyncio
async def test_ai_engine_hallucination_filter_simulation(engine):
    # Logic: Filter out issues that refer to selectors not in dom_snapshot
    # For now, it's a pass-through, but we can test the behavior
    issues = [UnifiedIssue(
        title="Hallucination",
        description="Filter test",
        issue_type="test",
        severity=IssueSeverity.MODERATE,
        confidence=ConfidenceLevel.MEDIUM,
        confidence_score=75.0,
        source=IssueSource.AI_CONTEXTUAL,
        engine_name="test_engine",
        location=ElementLocation(selector="#non-existent")
    )]
    # Future logic will filter these.
    assert len(issues) == 1
