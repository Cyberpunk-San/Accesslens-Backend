import pytest
from unittest.mock import AsyncMock, patch
from app.ai.llava_integration import LLaVAService
from app.ai.mistral_integration import MistralService

@pytest.mark.asyncio
async def test_llava_analysis_mock():
    # Note: LLaVAService doesn't actually use httpx in its current simulated implementation, 
    # but we can still test its method.
    service = LLaVAService()
    result = await service.analyze_image("fake_data", "Analyze this")
    assert "findings" in result
    assert result["findings"][0]["issue_type"] == "visual_clutter"

@pytest.mark.asyncio
async def test_mistral_analysis_mock():
    service = MistralService()
    result = await service.generate_fix("missing_alt context")
    assert "code_after" in result
    assert 'alt="Company logo - Home"' in result["code_after"]
