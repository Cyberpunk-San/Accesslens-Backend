import pytest

pytest.importorskip("torch")

import asyncio
from unittest.mock import Mock, patch, AsyncMock
from playwright.async_api import async_playwright
from app.engines.ai_engine import AIEngine
from app.ai.mistral_integration import MistralService
from app.ai.llava_integration import LLaVAService
from app.models.schemas import UnifiedIssue, IssueSeverity, IssueSource, ConfidenceLevel

@pytest.mark.asyncio
async def test_ai_service_initialization():
    """Test AI service initialization"""
    # This test might need adjustment based on how services are structured now
    from app.core.config import settings
    engine = AIEngine()
    assert engine.llava is not None
    assert engine.mistral is not None

@pytest.mark.asyncio
async def test_vision_prompt_building():
    """Test vision prompt construction"""
    engine = AIEngine()

    accessibility_tree = {
        "statistics": {
            "total_elements": 100,
            "images": {"total": 5}
        },
        "structure": {
            "focusable_elements": [1, 2, 3]
        }
    }

    prompt = engine._build_vision_prompt(accessibility_tree)
    
    # Update assertion to match actual prompt
    assert "Analyze the screenshot for accessibility issues" in prompt
    assert "100" in prompt

@pytest.mark.asyncio
async def test_fix_context_building():
    """Test fix context building"""
    engine = AIEngine()

    # Create a valid UnifiedIssue with all required fields
    issue = UnifiedIssue(
        title="Missing alt text",
        description="Image has no alt attribute",
        issue_type="missing_alt",
        severity=IssueSeverity.SERIOUS,
        confidence=ConfidenceLevel.HIGH,
        confidence_score=95,
        source=IssueSource.AI_CONTEXTUAL,
        engine_name="ai_engine",
        wcag_criteria=[]
    )

    context = engine._build_fix_context(issue, {})

    assert "Missing alt text" in context
    assert "HTML/ARIA fix" in context

@pytest.mark.asyncio
async def test_vision_results_parsing():
    """Test parsing vision analysis results"""
    engine = AIEngine()

    mock_results = {
        "findings": [
            {
                "issue_type": "visual_clutter",
                "description": "Page appears cluttered",
                "severity": "moderate",
                "location": "main content",
                "confidence": 0.85,
                "wcag_ref": "1.4.8",
                "suggestion": "Add more whitespace"
            }
        ]
    }

    issues = engine._parse_vision_results(mock_results, {})

    assert len(issues) == 1
    issue = issues[0]
    assert "vision_visual_clutter" in issue.issue_type
    assert issue.severity == IssueSeverity.MODERATE
    assert issue.confidence_score == 85
    assert issue.source == IssueSource.AI_CONTEXTUAL
    assert issue.engine_name == "ai_engine"

@pytest.mark.asyncio
async def test_ai_engine_with_mock_page():
    """Test AI engine with mock page"""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        html = """
        <html>
        <body>
            <h1>AI Test Page</h1>
            <p>Test content for AI vision analysis.</p>
            <img src="test_img.jpg" alt="A test image">
        </body>
        </html>
        """

        await page.set_content(html)

        screenshot = await page.screenshot(type="jpeg")
        import base64
        screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

        with patch.object(AIEngine, '_run_vision_analysis', return_value=[]):
            engine = AIEngine()

            issues = await engine.analyze(
                {
                    "page": page,
                    "screenshot": screenshot_b64,
                    "accessibility_tree": {
                        "statistics": {"total_elements": 10},
                        "structure": {}
                    }
                },
                {}
            )

            assert isinstance(issues, list)

        await browser.close()