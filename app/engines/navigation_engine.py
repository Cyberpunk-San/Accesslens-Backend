import logging
import asyncio
from typing import List, Dict, Any
from .base import BaseAccessibilityEngine
from ..models.schemas import (
    UnifiedIssue, IssueSeverity, IssueSource,
    ConfidenceLevel, ElementLocation, RemediationSuggestion,
    EvidenceData, AuditRequest, WCAGCriteria
)

logger = logging.getLogger(__name__)

class NavigationEngine(BaseAccessibilityEngine):
    """
    Simulates keyboard interaction to detect complex accessibility issues
    like focus traps, untabbable elements, missing focus indicators, and
    illogical focus order.
    """

    def __init__(self):
        super().__init__("navigation", "1.0.0")
        self.capabilities = ["keyboard", "focus", "interactivity"]

    async def analyze(
        self,
        page_data: Dict[str, Any],
        request: AuditRequest
    ) -> List[UnifiedIssue]:
        page = page_data.get("page")
        if not page:
            return []

        issues = []
        
        # 1. Landmark & Structural Integrity Check (using Accessibility Tree)
        tree = page_data.get("accessibility_tree", {})
        landmark_issues = self._check_landmarks(tree)
        issues.extend(landmark_issues)
        
        # 2. Focus Flow Analysis (Tab + Shift+Tab Simulation)
        flow_issues = await self._analyze_focus_flow(page)
        issues.extend(flow_issues)

        # 3. Visual Focus Indicator Check
        focus_indicator_issues = await self._check_focus_indicators(page)
        issues.extend(focus_indicator_issues)

        return issues



    def _check_landmarks(self, tree: Dict[str, Any]) -> List[UnifiedIssue]:
        """Validates landmark uniqueness and labeling using the Accessibility Tree."""
        issues = []
        if not tree: return []
        
        
        landmarks = []
        def traverse(node):
            role = node.get("role")
            if role in ["banner", "navigation", "main", "contentinfo", "search", "complementary", "form"]:
                landmarks.append({
                    "role": role,
                    "name": node.get("name", "").strip(),
                    "node_id": node.get("nodeId", "unknown")
                })
            for child in node.get("children", []):
                traverse(child)
        
        traverse(tree)
        
        # 1. Check for duplicate labels on the same landmark role
        seen_labels = {}
        for landmark in landmarks:
            key = (landmark["role"], landmark["name"])
            if landmark["name"]:
                if key in seen_labels:
                    issues.append(UnifiedIssue(
                        title=f"Duplicate landmark label: '{landmark['name']}'",
                        description=f"Multiple <{landmark['role']}> landmarks have the same accessible name '{landmark['name']}'. Screen reader users cannot distinguish between them.",
                        issue_type="DUPLICATE_LANDMARK_LABEL",
                        severity=IssueSeverity.SERIOUS,

                        confidence=ConfidenceLevel.HIGH,
                        confidence_score=95.0,
                        source=IssueSource.STRUCTURAL,
                        wcag_criteria=[WCAGCriteria(id="1.3.1", level="A", title="Info and Relationships")],
                        location=ElementLocation(selector=f"[role='{landmark['role']}']", html=f"Landmark Role: {landmark['role']}"),
                        remediation=RemediationSuggestion(
                            description=f"Provide a unique aria-label or aria-labelledby for each <{landmark['role']}> landmark used on the page.",
                            estimated_fix_hours=1.0,
                            verification_steps=[
                                "List all landmarks using a screen reader or browser tool",
                                "Verify each navigation/region has a distinct, descriptive name"
                            ]
                        ),
                        engine_name=self.name,
                        engine_version=self.version
                    ))
                seen_labels[key] = landmark
        
        # 2. Check for multiple 'main' landmarks
        main_landmarks = [l for l in landmarks if l["role"] == "main"]
        if len(main_landmarks) > 1:
            issues.append(UnifiedIssue(
                title="Multiple 'main' landmarks detected",
                description="The page contains more than one <main> landmark. Only one main content region should be present per page.",
                issue_type="MULTIPLE_MAIN_LANDMARKS",
                severity=IssueSeverity.SERIOUS,
                confidence=ConfidenceLevel.HIGH,
                confidence_score=100.0,
                source=IssueSource.STRUCTURAL,
                wcag_criteria=[WCAGCriteria(id="1.3.1", level="A", title="Info and Relationships")],
                remediation=RemediationSuggestion(
                    description="Ensure only one element has role='main' or is a <main> tag. Other regions should be wrapped in appropriate landmarks like 'section' or 'aside'.",
                    estimated_fix_hours=0.5,
                    verification_steps=["Remove redundant role='main' attributes", "Ensure the primary content is uniquely identified"]
                ),
                engine_name=self.name,
                engine_version=self.version
            ))
            
        return issues

    async def _analyze_focus_flow(self, page: Any) -> List[UnifiedIssue]:
        """Simulates Tab and Shift+Tab through the page and detects anomalies."""
        issues = []
        try:
            # Enhanced selector to include more interactive types
            focusable_selectors = await page.evaluate("""
                () => Array.from(document.querySelectorAll('a, button, input, select, textarea, [tabindex]:not([tabindex="-1"]), [role="button"], [role="link"], [role="menuitem"]'))
                           .filter(el => {
                               const style = window.getComputedStyle(el);
                               return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetWidth > 0;
                           })
                           .map(el => ({
                               id: el.id,
                               tagName: el.tagName,
                               text: el.innerText.trim().substring(0, 30),
                               html: el.outerHTML.substring(0, 100)
                           }))
            """)

            if not focusable_selectors:
                return []

            await page.keyboard.press('Home')
            await asyncio.sleep(0.5)

            tab_history = []
            max_tabs = min(len(focusable_selectors) * 2, 50)

            for i in range(max_tabs):
                current_focus_info = await page.evaluate("""
                    () => {
                        const el = document.activeElement;
                        return {
                            tagName: el.tagName,
                            id: el.id,
                            html: el.outerHTML.substring(0, 100),
                            text: el.innerText.trim().substring(0, 30)
                        };
                    }
                """)

                # Detect forward focus trap
                if len(tab_history) >= 3 and all(h['html'] == current_focus_info['html'] for h in tab_history[-2:]):
                    issues.append(UnifiedIssue(
                        title="Keyboard focus trap detected",
                        description=f"Keyboard focus is trapped on <{current_focus_info['tagName']}>. Focus does not move after 3 Tab presses.",
                        issue_type="FOCUS_TRAP",
                        severity=IssueSeverity.CRITICAL,
                        confidence=ConfidenceLevel.HIGH,
                        confidence_score=98.0,
                        source=IssueSource.HEURISTIC,
                        wcag_criteria=[WCAGCriteria(id="2.1.2", level="A", title="No Keyboard Trap")],
                        location=ElementLocation(
                            selector=f"#{current_focus_info['id']}" if current_focus_info['id'] else current_focus_info['tagName'],
                            html=current_focus_info['html']
                        ),
                        remediation=RemediationSuggestion(
                            description="Ensure all interactive elements can be exited via keyboard (Tab/Shift+Tab). Modals must trap focus within themselves but allow exit via Close button or Esc.",
                            estimated_fix_hours=4.0,
                            verification_steps=[
                                "Tab through the element and ensure focus moves to the next element",
                                "Shift+Tab to ensure focus moves to the previous element",
                                "Verify Escape key closes modal traps"
                            ]
                        ),
                        engine_name=self.name,
                        engine_version=self.version
                    ))
                    break

                tab_history.append(current_focus_info)
                await page.keyboard.press('Tab')
                await asyncio.sleep(0.15)

            # --- Shift+Tab reversal check ---
            # Attempt reverse; if focus doesn't move we flag it as a critical failure
            try:
                before_shift = await page.evaluate("() => ({ tagName: document.activeElement.tagName, id: document.activeElement.id, html: document.activeElement.outerHTML })")
                await page.keyboard.press('Shift+Tab')
                await asyncio.sleep(0.2)
                after_shift = await page.evaluate("() => ({ tagName: document.activeElement.tagName, id: document.activeElement.id, html: document.activeElement.outerHTML })")

                if before_shift['html'] == after_shift['html']:
                    issues.append(UnifiedIssue(
                        title="Shift+Tab reverse navigation broken",
                        description="Focus did not move backwards when Shift+Tab was pressed, indicating a one-directional focus trap.",
                        issue_type="REVERSE_FOCUS_TRAP",
                        severity=IssueSeverity.CRITICAL,
                        confidence=ConfidenceLevel.HIGH,
                        confidence_score=95.0,
                        source=IssueSource.HEURISTIC,
                        wcag_criteria=[WCAGCriteria(id="2.1.1", level="A", title="Keyboard Accessible")],
                        location=ElementLocation(selector="body", html=before_shift['html']),
                        remediation=RemediationSuggestion(
                            description="Ensure that Shift+Tab moves focus to the previous element. Check for custom keydown listeners that might be blocking the event.",
                            estimated_fix_hours=4.0,
                            verification_steps=["Hold Shift and press Tab", "Verify focus moves to the previous interactive element"]
                        ),
                        engine_name=self.name,
                        engine_version=self.version
                    ))
            except Exception:
                pass

            return issues

        except Exception as e:
            logger.error(f"Focus flow analysis failed: {e}")
            return []

    async def _check_focus_indicators(self, page: Any) -> List[UnifiedIssue]:
        """Checks for visible focus indicators with enriched remediation."""
        try:

            # Re-inject script with a small delay between focus and computation
            script = """
            async () => {
                const sleep = ms => new Promise(r => setTimeout(r, ms));
                const focusable = Array.from(document.querySelectorAll(
                    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
                )).filter(el => {
                    const s = window.getComputedStyle(el);
                    return s.display !== 'none' && s.visibility !== 'hidden' && el.offsetWidth > 0;
                });

                const noIndicator = [];
                for (const el of focusable.slice(0, 20)) {
                    const su = window.getComputedStyle(el);
                    const outlineU = su.outlineWidth + su.outlineStyle + su.outlineColor;
                    const borderU  = su.borderWidth  + su.borderStyle  + su.borderColor;
                    const shadowU  = su.boxShadow;

                    el.focus();
                    await sleep(30);

                    const s = window.getComputedStyle(el);
                    const outline = s.outlineWidth + s.outlineStyle + s.outlineColor;
                    const border  = s.borderWidth  + s.borderStyle  + s.borderColor;
                    const shadow  = s.boxShadow;

                    el.blur();

                    if (outline === outlineU && border === borderU && shadow === shadowU) {
                        noIndicator.push({
                            tag: el.tagName.toLowerCase(),
                            id: el.id || null,
                            html: el.outerHTML.substring(0, 100)
                        });
                    }
                }
                return noIndicator;
            }
            """
            findings = await page.evaluate(f"({script})()")
            issues = []
            seen_tags: set = set()
            for f in findings:
                key = (f['tag'], f['id'])
                if key in seen_tags:
                    continue
                seen_tags.add(key)
                selector = f"#{f['id']}" if f['id'] else f['tag']
                issues.append(UnifiedIssue(
                    title=f"Missing visible focus indicator: <{f['tag']}>",
                    description=f"The <{f['tag']}> element shows no detectable change in outline or border when focused.",
                    issue_type="MISSING_FOCUS_INDICATOR",
                    severity=IssueSeverity.SERIOUS,
                    confidence=ConfidenceLevel.MEDIUM,
                    confidence_score=78.0,
                    source=IssueSource.HEURISTIC,
                    wcag_criteria=[WCAGCriteria(id="2.4.7", level="AA", title="Focus Visible")],
                    location=ElementLocation(selector=selector, html=f['html']),
                    remediation=RemediationSuggestion(
                        description="Add a visible :focus style. Ensure it has at least 3:1 contrast against the background.",
                        code_after="*:focus { outline: 3px solid #005FCC; outline-offset: 2px; }",
                        estimated_fix_hours=2.0,
                        verification_steps=["Tab to the element", "Ensure a clearly visible border or outline appears"]
                    ),
                    engine_name=self.name,
                    engine_version=self.version
                ))
            return issues
        except Exception as e:
            logger.error(f"Focus indicator check failed: {e}")
            return []

    async def validate_config(self) -> bool:
        return True
