
from typing import List, Dict, Any, Optional
import asyncio
import logging
import base64
from dataclasses import dataclass, field
import json
import aiohttp

# Use explicit imports to avoid NameError issues in some environments
from app.models.schemas import (
    UnifiedIssue, IssueSource, ConfidenceLevel, IssueSeverity,
    RemediationSuggestion, EvidenceData, WCAGCriteria, ElementLocation
)
from app.core.scoring import ConfidenceCalculator
from app.core.config import settings

@dataclass
class AIConfig:
    llava_endpoint: str = field(default_factory=lambda: settings.llava_endpoint)
    mistral_endpoint: str = field(default_factory=lambda: settings.mistral_endpoint)
    use_local: bool = field(default_factory=lambda: settings.ai_use_local)
    confidence_threshold: float = field(default_factory=lambda: settings.ai_confidence_threshold)

class AIService:
    """
    AI-powered accessibility analysis service.
    """
    def __init__(self, config: Optional[AIConfig] = None):
        self.config = config or AIConfig()
        self._logger = logging.getLogger(__name__)

    async def analyze(
        self,
        screenshot_b64: str,
        dom_snapshot: Dict,
        existing_issues: List[UnifiedIssue]
    ) -> List[UnifiedIssue]:
        """
        Analyze page via AI. Signature matches what the hardened tests expect.
        """
        new_issues = []
        
        # 1. Vision check
        if self.config.llava_endpoint:
            vision_results = await self._call_llava_api(screenshot_b64, "High-level scan")
            if vision_results:
                new_issues = self._parse_vision_results(vision_results)

        # 2. Enrich ALL issues with fixes using Mistral
        if self.config.mistral_endpoint:
            all_to_fix = new_issues + existing_issues
            for issue in all_to_fix:
                fix_data = await self._call_mistral_api(f"Fix issue: {issue.title}")
                if fix_data:
                    issue.remediation = RemediationSuggestion(
                        description=fix_data.get("explanation", "AI suggested fix"),
                        code_after=fix_data.get("code_after", ""),
                        estimated_effort=self._estimate_effort(fix_data.get("code_after", ""))
                    )
        
        return new_issues

    def _parse_vision_results(self, result: Dict) -> List[UnifiedIssue]:
        issues = []
        for finding in result.get("findings", []):
            sev_str = finding.get("severity", "moderate").lower()
            severity = getattr(IssueSeverity, sev_str.upper(), IssueSeverity.MODERATE)
            
            conf_val = finding.get("confidence", 0.7)
            if conf_val >= 0.95: confidence = ConfidenceLevel.HIGH
            elif conf_val >= 0.7: confidence = ConfidenceLevel.MEDIUM
            else: confidence = ConfidenceLevel.LOW
            
            issues.append(UnifiedIssue(
                title=f"[AI Vision] {finding.get('description', 'Issue detected')[:50]}",
                description=finding.get("description", ""),
                issue_type=finding.get("issue_type", "AI_VISION_DETECTION"),
                severity=severity,
                confidence=confidence,
                confidence_score=conf_val * 100,
                source=IssueSource.AI_CONTEXTUAL,
                engine_name="aiservice",
                engine_version="1.0.0"
            ))
        return issues

    def _estimate_effort(self, code: str) -> str:
        lines = code.strip().count("\n") + 1 if code else 0
        if lines == 0: return "unknown"
        if lines < 3: return "low"
        if lines < 10: return "medium"
        return "high"

    def _map_to_wcag(self, issue_type: str) -> str:
        mapping = {"spacing": "1.4.12", "clutter": "1.3.1"}
        return mapping.get(issue_type, "1.3.1")

    async def _call_llava_api(self, screenshot: str, prompt: str) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.config.llava_endpoint, json={"image": screenshot, "prompt": prompt}) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            self._logger.error(f"LLaVA error: {e}")
        return None

    async def _call_mistral_api(self, prompt: str) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.config.mistral_endpoint, json={"prompt": prompt}) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            self._logger.error(f"Mistral error: {e}")
        return None