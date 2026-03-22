
from typing import List, Dict, Any, Optional
import asyncio
import logging
import time
from datetime import datetime

from ..models.schemas import (
    AuditRequest, AuditReport, UnifiedIssue, AuditSummary,
    IssueSeverity, IssueSource
)
from ..engines.registry import EngineRegistry
from .page_controller import PageController
from .accessibility_tree import AccessibilityTreeExtractor
from .browser_manager import browser_manager
from ..core.scoring import ConfidenceCalculator
from .config import settings

class AuditOrchestrator:


    def __init__(self, engine_registry: EngineRegistry):
        self.engine_registry = engine_registry
        self.page_controller = PageController()
        self.tree_extractor = AccessibilityTreeExtractor()
        self._logger = logging.getLogger(__name__)

    async def run_audit(self, request: AuditRequest) -> AuditReport:

        start_time = time.time()
        page = None

        self._logger.info(f"Starting audit for {request.url}")

        try:
            page_data = await self._setup_page(request)
            page = page_data.get("page")

            if "error" in page_data:
                return self._create_error_report(request, page_data["error"])

            engines_to_run = list(request.engines)
            if request.enable_ai and settings.enable_ai_engine and "ai_engine" not in engines_to_run and "ai" not in engines_to_run:
                engines_to_run.append("ai_engine")

            engine_tasks = []
            for engine_name in engines_to_run:
                engine = self.engine_registry.get(engine_name)
                if engine:
                    engine_tasks.append(
                        self._run_engine_safe(engine, page_data, request)
                    )
                else:
                    self._logger.debug(f"Engine '{engine_name}' not found in registry — skipping")


            engine_results = await asyncio.gather(*engine_tasks, return_exceptions=True)


            all_issues = []
            for result in engine_results:
                if isinstance(result, Exception):
                    self._logger.error(f"Engine failed: {result}")
                elif isinstance(result, list):
                    all_issues.extend(result)


            summary = self._generate_summary(all_issues, start_time)


            report = AuditReport(
                request=request,
                summary=summary,
                issues=all_issues,
                accessibility_tree=page_data.get("accessibility_tree"),
                metadata={
                    "duration_seconds": round(time.time() - start_time, 2),
                    "engines_run": request.engines,
                    "full_screenshot": page_data.get("screenshot")
                }
            )

            self._logger.info(f"Audit complete: {summary.total_issues} issues found")
            return report

        finally:
            if page:
                await browser_manager.release_page(page)

    async def _setup_page(self, request: AuditRequest) -> Dict[str, Any]:

        try:
            page_data = await self.page_controller.navigate_and_extract(
                request.url,
                {
                    "viewport": request.viewport,
                    "wait_for_network_idle": request.wait_for_network_idle,
                    "timeout": settings.browser_timeout
                }
            )

            # Important: Attach the live page object so engines can perform real analysis
            # PageController no longer releases the page in its finally block.
            if self.page_controller._current_page:
                page_data["page"] = self.page_controller._current_page

            return page_data

        except Exception as e:
            self._logger.error(f"Page setup failed for {request.url}: {e}")
            return {"error": f"Failed to load page: {str(e)}"}
        finally:

            pass

    async def _run_engine_safe(
        self,
        engine,
        page_data: Dict[str, Any],
        request: AuditRequest
    ) -> List[UnifiedIssue]:

        try:
            self._logger.debug(f"Running engine: {engine.name}")
            # Fix: Pass the request object directly, not as a dictionary
            # Engines like WCAGEngine expect the AuditRequest object for typing.
            issues = await engine.analyze(page_data, request)
            self._logger.debug(f"Engine {engine.name} found {len(issues)} issues")
            return issues
        except Exception as e:
            self._logger.error(f"Engine {engine.name} failed: {e}", exc_info=True)
            return []



    def _generate_summary(
        self,
        issues: List[UnifiedIssue],
        start_time: float
    ) -> AuditSummary:

        by_severity = {severity: 0 for severity in IssueSeverity}
        by_source = {source: 0 for source in IssueSource}
        by_wcag_level = {"A": 0, "AA": 0, "AAA": 0}

        total_confidence = 0

        for issue in issues:
            by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1
            by_source[issue.source] = by_source.get(issue.source, 0) + 1
            total_confidence += issue.confidence_score

            for wcag in issue.wcag_criteria:
                by_wcag_level[wcag.level] = by_wcag_level.get(wcag.level, 0) + 1

        # --- Improved scoring formula ---
        # Deduct per unique issue TYPE (not per instance) to avoid score=0 on large sites.
        # Weight each deduction by the issue's confidence so low-confidence guesses hurt less.
        if issues:
            severity_weights = {
                IssueSeverity.CRITICAL: 20,
                IssueSeverity.SERIOUS:  10,
                IssueSeverity.MODERATE:  5,
                IssueSeverity.MINOR:     2
            }

            # Group by (severity, issue_type) and deduct only once per unique violation type.
            seen_types: set = set()
            total_deduction = 0.0
            for issue in sorted(issues, key=lambda i: severity_weights.get(i.severity, 2), reverse=True):
                key = (issue.severity, issue.issue_type)
                if key not in seen_types:
                    seen_types.add(key)
                    weight = severity_weights.get(issue.severity, 2)
                    # Scale deduction by confidence (0–1 range)
                    confidence_factor = issue.confidence_score / 100.0
                    total_deduction += weight * confidence_factor

            # Cap total deduction at 70 so even very broken pages still show a non-zero score
            score = max(0, 100 - min(70, total_deduction))
        else:
            score = 100

        avg_confidence = total_confidence / len(issues) if issues else 100

        axe_issues = [i for i in issues if i.source == IssueSource.WCAG_DETERMINISTIC]
        advanced_issues = [i for i in issues if i.source != IssueSource.WCAG_DETERMINISTIC]

        coverage_comparator = {
            "axe_only_found": len(axe_issues),
            "advanced_found": len(advanced_issues),
            "axe_coverage_percent": round(len(axe_issues) / len(issues) * 100, 2) if issues else 100
        }

        # Extract contrast patterns from ContrastEngine if it ran
        contrast_patterns = []
        contrast_engine = self.engine_registry.get("contrast_engine")
        if contrast_engine and hasattr(contrast_engine, "_last_patterns"):
            contrast_patterns = contrast_engine._last_patterns

        return AuditSummary(
            total_issues=len(issues),
            by_severity=by_severity,
            by_source=by_source,
            by_wcag_level=by_wcag_level,
            score=round(score, 2),
            confidence_avg=round(avg_confidence, 2),
            coverage_comparator=coverage_comparator,
            contrast_patterns=contrast_patterns
        )

    def _create_error_report(self, request: AuditRequest, error: str) -> AuditReport:

        return AuditReport(
            request=request,
            summary=AuditSummary(
                total_issues=0,
                by_severity={s: 0 for s in IssueSeverity},
                by_source={s: 0 for s in IssueSource},
                by_wcag_level={"A": 0, "AA": 0, "AAA": 0},
                score=0,
                confidence_avg=0,
                error=error
            ),
            issues=[],
            metadata={"error": error}
        )