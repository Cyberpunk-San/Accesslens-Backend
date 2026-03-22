import pytest
from app.engines.wcag_engine import WCAGEngine
from unittest.mock import MagicMock, AsyncMock
from app.models.schemas import UnifiedIssue, IssueSeverity, IssueSource, ConfidenceLevel, WCAGCriteria, WCAGLevel

class MockAxeNode:
    """Mock axe-core node"""
    def __init__(self, target, html):
        self.target = target
        self.html = html
        self.failureSummary = "Mock failure summary"
    
    def get(self, key, default=None):
        """Mock the get method that _convert_violation expects"""
        if key == "target":
            return self.target
        elif key == "html":
            return self.html
        elif key == "failureSummary":
            return self.failureSummary
        return default

class MockAxeViolation:
    """Mock axe-core violation"""
    def __init__(self, rule_id, impact, tags, help_text, help_url):
        self.id = rule_id
        self.impact = impact
        self.tags = tags
        self.help = help_text
        self.description = "Mock description"
        self.helpUrl = help_url
        self.nodes = []

@pytest.mark.asyncio
async def test_wcag_violation_conversion():
    """Test WCAG violation conversion to UnifiedIssue"""
    engine = WCAGEngine()
    
    # Create mock violation with proper structure
    mock_violation = MockAxeViolation(
        rule_id="image-alt",
        impact="critical",
        tags=["wcag2a", "wcag111", "cat.text-alternatives"],
        help_text="Images must have alternate text",
        help_url="https://dequeuniversity.com/rules/axe/4.8/image-alt"
    )
    
    # Add mock node
    mock_node = {
        "target": ["#logo", "/html[1]/body[1]/div[1]/img[1]"],
        "html": "<img src='logo.png'>",
        "failureSummary": "Mock failure summary"
    }
    mock_violation.nodes = [mock_node]
    
    # Create mock page
    mock_page = AsyncMock()
    mock_page.query_selector = AsyncMock(return_value=None)
    
    # Convert violation to issue
    issue = await engine._convert_violation(mock_violation, mock_node, mock_page)
    
    # Assertions
    assert issue is not None
    assert issue.title == "Images must have alternate text"
    assert issue.severity == IssueSeverity.CRITICAL  # Use enum, not string
    assert issue.source == IssueSource.WCAG_DETERMINISTIC
    assert issue.engine_name == "wcag_deterministic"
    
    # Check WCAG criteria
    assert len(issue.wcag_criteria) > 0
    
    # Check that at least one criteria has a valid ID
    criteria_ids = [c.id for c in issue.wcag_criteria]
    assert any(criteria_ids), "No WCAG criteria IDs found"
    
    # Check for 1.1.1 (should be parsed from wcag111)
    found_111 = False
    for c in issue.wcag_criteria:
        if c.id == "1.1.1":
            found_111 = True
            # Verify level is correct enum value
            assert c.level in ["A", "AA", "AAA"]  # String representation
            break
    
    assert found_111, "WCAG 1.1.1 not found in criteria"
    
    # Check remediation
    assert issue.remediation is not None
    assert "alt" in issue.remediation.code_after.lower()
