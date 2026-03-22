import pytest
import json
import base64
from unittest.mock import MagicMock, patch, AsyncMock
from app.ai.ai_service import AIService, AIConfig
from app.models.schemas import UnifiedIssue, IssueSeverity, ConfidenceLevel, IssueSource
pytestmark = [pytest.mark.browser, pytest.mark.high_coverage]

@pytest.fixture
def ai_service():
    config = AIConfig(
        llava_endpoint="http://mock-llava:8001",
        mistral_endpoint="http://mock-mistral:8002",
        use_local=True
    )
    return AIService(config=config)

@pytest.mark.asyncio
async def test_ai_service_analyze_full_flow(ai_service):
    # Prepare responses
    vision_response = {
        "findings": [
            {
                "description": "Critical color reliance error",
                "severity": "critical",
                "confidence": 0.96,
                "issue_type": "AI_VISION"
            }
        ]
    }
    fix_response = {"explanation": "Fix explanation", "code_after": "<div>fixed</div>"}
    
    # Manual injection for absolute stability
    ai_service._call_llava_api = AsyncMock(return_value=vision_response)
    ai_service._call_mistral_api = AsyncMock(return_value=fix_response)
    results = await ai_service.analyze("fake_b64", {}, [])
    assert len(results) == 1
    assert results[0].severity == IssueSeverity.CRITICAL
    assert results[0].remediation.code_after == "<div>fixed</div>"

@pytest.mark.asyncio
async def test_ai_service_vision_error_handling(ai_service):
    ai_service._call_llava_api = AsyncMock(return_value=None)
    results = await ai_service.analyze("fake_b64", {}, [])
    assert results == []

@pytest.mark.asyncio
async def test_ai_service_parse_vision_results_varied_confidence(ai_service):
    mock_result = {
        "findings": [
            {"confidence": 0.99, "issue_type": "t1"},
            {"confidence": 0.82, "issue_type": "t2"},
            {"confidence": 0.10, "issue_type": "t3"}
        ]
    }
    issues = ai_service._parse_vision_results(mock_result)
    assert issues[0].confidence == ConfidenceLevel.HIGH # >= 0.95
    assert issues[1].confidence == ConfidenceLevel.MEDIUM # >= 0.70
    assert issues[2].confidence == ConfidenceLevel.LOW
