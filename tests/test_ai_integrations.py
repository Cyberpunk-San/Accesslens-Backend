import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp
from app.ai.ai_service import AIService, AIConfig
from app.ai.llava_integration import LLaVAService
from app.ai.mistral_integration import MistralService
from app.models.schemas import UnifiedIssue, IssueSeverity, ConfidenceLevel, IssueSource, RemediationSuggestion

pytestmark = pytest.mark.unit

# --- AIService Tests ---

@pytest.fixture
def ai_service():
    config = AIConfig(
        llava_endpoint="http://llava:11434",
        mistral_endpoint="http://mistral:11434"
    )
    return AIService(config=config)

@pytest.mark.asyncio
async def test_ai_service_analyze_full_flow(ai_service):
    screenshot = "base64data"
    dom = {"some": "dom"}
    existing_issue = UnifiedIssue(
        title="Existing", description="desc", issue_type="low_contrast",
        severity=IssueSeverity.SERIOUS, confidence=ConfidenceLevel.HIGH, confidence_score=95.0,
        source=IssueSource.CONTRAST, engine_name="test", engine_version="1.0"
    )

    # Mock LLaVA response
    llava_resp = {
        "findings": [
            {"description": "Too much clutter", "severity": "serious", "confidence": 0.98, "issue_type": "CLUTTER"}
        ]
    }
    
    # Mock Mistral response
    mistral_resp = {
        "explanation": "Simplified fix",
        "code_after": "<div>Fixed</div>"
    }

    with patch("aiohttp.ClientSession.post") as mock_post:
        # Mocking the context manager for aiohttp
        mock_resp_llava = AsyncMock()
        mock_resp_llava.status = 200
        mock_resp_llava.json.return_value = llava_resp
        mock_resp_llava.__aenter__.return_value = mock_resp_llava
        
        mock_resp_mistral = AsyncMock()
        mock_resp_mistral.status = 200
        mock_resp_mistral.json.return_value = mistral_resp
        mock_resp_mistral.__aenter__.return_value = mock_resp_mistral
        
        # Side effect to return llava then mistral then mistral (for each issue)
        mock_post.side_effect = [mock_resp_llava, mock_resp_mistral, mock_resp_mistral]
        
        results = await ai_service.analyze(screenshot, dom, [existing_issue])
        
        assert len(results) == 1
        assert results[0].issue_type == "CLUTTER"
        assert results[0].confidence == ConfidenceLevel.HIGH
        # Verify enrichment
        assert results[0].remediation.description == "Simplified fix"
        assert existing_issue.remediation.description == "Simplified fix"

@pytest.mark.asyncio
async def test_ai_service_api_errors(ai_service):
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.side_effect = Exception("Network Down")
        results = await ai_service.analyze("img", {}, [])
        assert results == []

@pytest.mark.asyncio
async def test_ai_service_status_not_200(ai_service):
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_resp = AsyncMock()
        mock_resp.status = 500
        mock_resp.__aenter__.return_value = mock_resp
        mock_post.return_value = mock_resp
        
        results = await ai_service.analyze("img", {}, [])
        assert results == []

def test_ai_service_estimate_effort(ai_service):
    assert ai_service._estimate_effort("") == "unknown"
    assert ai_service._estimate_effort("line1\nline2") == "low"
    assert ai_service._estimate_effort("\n".join(["line"] * 5)) == "medium"
    assert ai_service._estimate_effort("\n".join(["line"] * 15)) == "high"

def test_ai_service_map_to_wcag(ai_service):
    assert ai_service._map_to_wcag("spacing") == "1.4.12"
    assert ai_service._map_to_wcag("other") == "1.3.1"

# --- LLaVAService Tests ---

@pytest.mark.asyncio
async def test_llava_integration_lifecycle():
    with patch("torch.cuda.is_available", return_value=False):
        service = LLaVAService(device="cpu")
        assert service.device == "cpu"
        
        await service.load_model()
        assert service._model == "llava-loaded"
        
        res = await service.analyze_image("data", "prompt")
        assert "findings" in res
        
        await service.unload_model()
        assert service._model is None

@pytest.mark.asyncio
async def test_llava_cuda_detection():
    with patch("torch.cuda.is_available", return_value=True):
        service = LLaVAService()
        assert service.device == "cuda"
        # Test unload empty cache path
        with patch("torch.cuda.empty_cache") as mock_empty:
            service._model = "dummy"
            await service.unload_model()
            mock_empty.assert_called_once()

# --- MistralService Tests ---

@pytest.mark.asyncio
async def test_mistral_integration_lifecycle():
    service = MistralService(device="cpu")
    await service.load_model()
    
    # Test different scenarios for simulate_fix
    res_alt = await service.generate_fix("missing_alt")
    assert "alt=" in res_alt["code_after"]
    
    res_contrast = await service.generate_fix("low_contrast")
    assert "#555" in res_contrast["code_after"]
    
    res_button = await service.generate_fix("empty_button")
    assert "aria-label" in res_button["code_after"]
    
    res_heading = await service.generate_fix("heading_skip")
    assert "<h2>" in res_heading["code_after"]
    
    res_default = await service.generate_fix("random")
    assert "proper accessible attributes" in res_default["explanation"]

@pytest.mark.asyncio
async def test_mistral_error_handling():
    service = MistralService(device="cpu")
    with patch.object(service, "_simulate_fix_generation", side_effect=ValueError("Boom")):
        res = await service.generate_fix("any")
        assert res is None
