import logging
from typing import List, Dict, Any
from .base import BaseAccessibilityEngine
from ..models.schemas import (
    UnifiedIssue, IssueSeverity, IssueSource,
    ConfidenceLevel, ElementLocation, RemediationSuggestion,
    EvidenceData, AuditRequest, WCAGCriteria
)
from ..core.scoring import ConfidenceCalculator
from ..core.config import settings

logger = logging.getLogger(__name__)

class FormEngine(BaseAccessibilityEngine):
    """
    Dedicated engine for validating form accessibility.
    Checks for label associations, placeholder misuse, and error message linkages.
    """

    def __init__(self):
        super().__init__("form_engine", "1.0.0")
        self.capabilities = ["forms", "inputs", "labels"]

    async def analyze(
        self,
        page_data: Dict[str, Any],
        request: AuditRequest
    ) -> List[UnifiedIssue]:
        page = page_data.get("page")
        if not page:
            return []

        issues = []
        
        # 1. Label Association Check
        label_issues = await self._check_label_association(page)
        issues.extend(label_issues)
        
        # 2. Placeholder-as-Label Check
        placeholder_issues = await self._check_placeholder_misuse(page)
        issues.extend(placeholder_issues)
        
        # 3. Error Association Check (aria-describedby)
        error_issues = await self._check_error_association(page)
        issues.extend(error_issues)

        return issues

    async def _check_label_association(self, page: Any) -> List[UnifiedIssue]:
        """Verifies that every input has an associated <label>."""
        script = """
        () => {
            const results = [];
            const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea'));
            
            inputs.forEach(input => {
                let hasLabel = false;
                
                // 1. Explicit label via 'for'
                if (input.id) {
                    const label = document.querySelector(`label[for="${input.id}"]`);
                    if (label && label.innerText.trim()) hasLabel = true;
                }
                
                // 2. Implicit label (wrapped)
                if (!hasLabel && input.closest('label')) {
                    if (input.closest('label').innerText.trim()) hasLabel = true;
                }
                
                // 3. Aria-label/labelledby
                if (!hasLabel && (input.getAttribute('aria-label') || input.getAttribute('aria-labelledby'))) {
                    hasLabel = true;
                }

                if (!hasLabel) {
                    results.push({
                        id: input.id || 'no-id',
                        tag: input.tagName.toLowerCase(),
                        type: input.type,
                        selector: input.id ? '#' + input.id : input.tagName.toLowerCase(),
                        html: input.outerHTML.substring(0, 100)
                    });
                }
            });
            return results;
        }
        """
        try:
            findings = await page.evaluate(script)
            issues = []
            for f in findings:
                issues.append(UnifiedIssue(
                    title=f"Input field lacks associated label: <{f['tag']}>",
                    description=f"This {f['tag']} (type: {f['type']}) does not have a programmatically associated label, aria-label, or aria-labelledby. Screen readers will not announce its purpose clearly.",
                    issue_type="MISSING_LABEL",
                    severity=IssueSeverity.CRITICAL,
                    confidence=ConfidenceLevel.HIGH,
                    confidence_score=98.0,
                    source=IssueSource.HEURISTIC,
                    wcag_criteria=[WCAGCriteria(id="3.3.2", level="A", title="Labels or Instructions", description="Labels or instructions are provided when content requires user input")],
                    location=ElementLocation(selector=f['selector'], html=f['html']),
                    remediation=RemediationSuggestion(
                        description="Use a <label> element with a 'for' attribute matching the input's 'id', or wrap the input inside a <label> element.",
                        code_after=f'<label for="{f["id"] if f["id"] != "no-id" else "input-id"}">Label Text</label>\n<input id="{f["id"] if f["id"] != "no-id" else "input-id"}">',
                        estimated_effort="Low"
                    ),
                    engine_name=self.name,
                    engine_version=self.version
                ))
            return issues
        except Exception as e:
            logger.error(f"Label association check failed: {e}")
            return []

    async def _check_placeholder_misuse(self, page: Any) -> List[UnifiedIssue]:
        """Detects inputs using placeholder as the only label."""
        script = """
        () => {
            const results = [];
            const inputs = Array.from(document.querySelectorAll('input[placeholder], textarea[placeholder]'));
            
            inputs.forEach(input => {
                const placeholder = input.getAttribute('placeholder').trim();
                if (!placeholder) return;

                let hasLabel = false;
                if (input.id && document.querySelector(`label[for="${input.id}"]`)) hasLabel = true;
                if (!hasLabel && input.closest('label')) hasLabel = true;
                if (!hasLabel && (input.getAttribute('aria-label') || input.getAttribute('aria-labelledby'))) hasLabel = true;

                if (placeholder && !hasLabel) {
                    results.push({
                        placeholder: placeholder,
                        selector: input.id ? '#' + input.id : input.tagName.toLowerCase(),
                        html: input.outerHTML.substring(0, 100)
                    });
                }
            });
            return results;
        }
        """
        try:
            findings = await page.evaluate(script)
            issues = []
            for f in findings:
                issues.append(UnifiedIssue(
                    title="Placeholder used as label",
                    description=f"The input uses '{f['placeholder']}' as a placeholder but has no real label. Placeholders disappear when the user starts typing and are often not accessible to screen readers.",
                    issue_type="PLACEHOLDER_MISUSE",
                    severity=IssueSeverity.MODERATE,
                    confidence=ConfidenceLevel.HIGH,
                    confidence_score=95.0,
                    source=IssueSource.HEURISTIC,
                    location=ElementLocation(selector=f['selector'], html=f['html']),
                    remediation=RemediationSuggestion(
                        description="Placeholders should not be used as the primary label. Add a persistent <label> element.",
                        estimated_effort="Low"
                    ),
                    engine_name=self.name,
                    engine_version=self.version
                ))
            return issues
        except Exception as e:
            logger.error(f"Placeholder check failed: {e}")
            return []

    async def _check_error_association(self, page: Any) -> List[UnifiedIssue]:
        """
        Checks for inputs with error messages that aren't linked via aria-describedby,
        and verifies if 'required' inputs have clear instructions. (Point 8)
        """
        script = """
        () => {
            const results = [];
            const inputs = Array.from(document.querySelectorAll('input, select, textarea'));
            
            inputs.forEach(input => {
                const isRequired = input.hasAttribute('required') || input.getAttribute('aria-required') === 'true';
                const hasDescribedBy = input.getAttribute('aria-describedby');
                
                // 1. Check for nearby error messages not linked
                const parent = input.parentElement;
                let nearbyError = false;
                if (parent) {
                    const errorElement = parent.querySelector('.error, .error-message, [class*="error"], [id*="error"]');
                    const text = parent.innerText.toLowerCase();
                    if (errorElement || text.includes('error') || text.includes('required')) {
                        nearbyError = true;
                    }
                }
                
                if (nearbyError && !hasDescribedBy) {
                    results.push({
                        type: 'missing_error_link',
                        selector: getUniqueSelector(input),
                        html: input.outerHTML.substring(0, 100)
                    });
                }
                
                // 2. Check for required fields without instructions
                if (isRequired) {
                    const label = document.querySelector(`label[for="${input.id}"]`) || input.closest('label');
                    const labelText = label ? label.innerText.toLowerCase() : '';
                    if (!labelText.includes('*') && !labelText.includes('required') && !hasDescribedBy) {
                        results.push({
                            type: 'missing_required_instruction',
                            selector: getUniqueSelector(input),
                            html: input.outerHTML.substring(0, 100)
                        });
                    }
                }
            });
            return results;

            function getUniqueSelector(el) {
                if (el.id) return `#${CSS.escape(el.id)}`;
                let path = [];
                while (el && el.nodeType === Node.ELEMENT_NODE) {
                    let selector = el.tagName.toLowerCase();
                    const siblings = Array.from(el.parentNode ? el.parentNode.children : []).filter(c => c.tagName === el.tagName);
                    if (siblings.length > 1) {
                        const index = siblings.indexOf(el) + 1;
                        selector += `:nth-child(${index})`;
                    }
                    path.unshift(selector);
                    el = el.parentNode;
                }
                return path.join(' > ');
            }
        }
        """
        try:
            findings = await page.evaluate(script)
            issues = []
            for f in findings:
                if f['type'] == 'missing_error_link':
                    issues.append(UnifiedIssue(
                        title="Inaccessible error message",
                        description="This input appears to have an error message nearby, but it is not programmatically linked via 'aria-describedby'. Screen reader users will not hear the error when focus enters the input.",
                        issue_type="MISSING_ERROR_LINK",
                        severity=IssueSeverity.SERIOUS,
                        confidence=ConfidenceLevel.MEDIUM,
                        confidence_score=70.0,
                        source=IssueSource.HEURISTIC,
                        wcag_criteria=[WCAGCriteria(id="3.3.1", level="A", title="Error Identification")],
                        location=ElementLocation(selector=f['selector'], html=f['html']),
                        remediation=RemediationSuggestion(
                            description="Use 'aria-describedby' to link the input to the element containing the error message.",
                            code_after='<input aria-describedby="error-id">\n<div id="error-id">Error message text</div>',
                            estimated_effort="Low"
                        ),
                        engine_name=self.name,
                        engine_version=self.version
                    ))
                elif f['type'] == 'missing_required_instruction':
                    issues.append(UnifiedIssue(
                        title="Missing required field instruction",
                        description="This input is marked as required, but there is no clear visual or programmatic instruction (like an asterisk or 'required' text in the label).",
                        issue_type="MISSING_INSTRUCTION",
                        severity=IssueSeverity.MODERATE,
                        confidence=ConfidenceLevel.MEDIUM,
                        confidence_score=75.0,
                        source=IssueSource.HEURISTIC,
                        wcag_criteria=[WCAGCriteria(id="3.3.2", level="A", title="Labels or Instructions")],
                        location=ElementLocation(selector=f['selector'], html=f['html']),
                        remediation=RemediationSuggestion(
                            description="Add '(required)' or an asterisk (*) to the label text, and ensure it's explained at the top of the form.",
                            code_after='<label for="name">Name (required)</label>\n<input id="name" required>',
                            estimated_effort="Low"
                        ),
                        engine_name=self.name,
                        engine_version=self.version
                    ))
            return issues
        except Exception as e:
            logger.error(f"Error association check failed: {e}")
            return []

    async def validate_config(self) -> bool:
        return True
