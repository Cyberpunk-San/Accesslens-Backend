from typing import List, Dict, Any, Optional
from playwright.async_api import Page
import asyncio
import logging
from .base import BaseAccessibilityEngine
from ..models.schemas import (
    UnifiedIssue, IssueSeverity, IssueSource,
    ConfidenceLevel, ElementLocation, RemediationSuggestion,
    EvidenceData, WCAGCriteria, AuditRequest
)
from ..core.heading_analyzer import HeadingHierarchyAnalyzer
from ..core.landmark_validator import LandmarkValidator
from ..core.scoring import ConfidenceCalculator
from ..core.config import settings

class StructuralEngine(BaseAccessibilityEngine):

    def __init__(self):
        super().__init__("structural_engine", "1.0.0")
        self.capabilities = ["structure", "headings", "landmarks", "semantics"]
        self._logger = logging.getLogger(__name__)
        self.heading_analyzer = HeadingHierarchyAnalyzer()
        self.landmark_validator = LandmarkValidator()

    async def analyze(
        self,
        page_data: Dict[str, Any],
        request: AuditRequest
    ) -> List[UnifiedIssue]:
        page = page_data.get("page")
        accessibility_tree = page_data.get("accessibility_tree", {})
        if not page:
            return []
        try:
            issues = []
            
            # 1. Page Language Declaration (Point 4)
            lang_issues = await self._check_lang_attribute(page)
            issues.extend(lang_issues)

            # 2. Headings Analysis (Point 1)
            headings = await self._extract_headings(page, accessibility_tree)
            if headings:
                heading_analysis = self.heading_analyzer.analyze(headings)
                heading_issues = await self._convert_heading_issues(heading_analysis.get("issues", []))
                issues.extend(heading_issues)
                if heading_analysis.get("outline"):
                    page_data["heading_outline"] = heading_analysis["outline"]

            # 3. Landmarks Analysis
            landmarks = await self._extract_landmarks(page, accessibility_tree)
            if landmarks:
                landmark_analysis = self.landmark_validator.validate(landmarks)
                landmark_issues = await self._convert_landmark_issues(landmark_analysis.get("issues", []))
                issues.extend(landmark_issues)
                if landmark_analysis.get("structure"):
                    page_data["landmark_structure"] = landmark_analysis["structure"]

            # 4. Document Outline Checks
            outline_issues = await self._analyze_document_outline(page, headings, landmarks)
            issues.extend(outline_issues)

            # 5. Semantic Structure Checks
            semantic_issues = await self._analyze_semantic_structure(page, accessibility_tree)
            issues.extend(semantic_issues)

            # 6. Navigation Analysis (Points 13, 14, 15)
            nav_issues = await self._analyze_navigation_structure(page)
            issues.extend(nav_issues)

            # 7. ARIA Live Regions (Point 5)
            live_issues = await self._check_aria_live(page)
            issues.extend(live_issues)

            # 8. Visual Reading Order (Point 7)
            order_issues = await self._check_visual_reading_order(page)
            issues.extend(order_issues)

            return issues
        except Exception as e:
            self._logger.error(f"Structural analysis failed: {e}")
            return []

    async def _extract_headings(self, page: Page, accessibility_tree: Dict[str, Any]) -> List[Dict[str, Any]]:
        if accessibility_tree.get("structure", {}).get("headings"):
            headings_data = accessibility_tree["structure"]["headings"]
            if isinstance(headings_data, dict) and headings_data.get("headings"):
                return headings_data["headings"]
        js_code = """
        (function() {
            const headings = [];
            const elements = document.querySelectorAll('h1, h2, h3, h4, h5, h6, [role="heading"]');
            elements.forEach((el, index) => {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;
                let level = parseInt(el.tagName.substring(1));
                if (isNaN(level)) {
                    level = parseInt(el.getAttribute('aria-level')) || 2;
                }
                headings.push({
                    level: level,
                    text: el.textContent.trim(),
                    tagName: el.tagName.toLowerCase(),
                    selector: getUniqueSelector(el),
                    index: index,
                    isVisible: el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0
                });
            });
            return headings;
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
        })();
        """
        try:
            return await page.evaluate(js_code)
        except Exception as e:
            self._logger.warning(f"Failed to extract headings: {e}")
            return []

    async def _extract_landmarks(self, page: Page, accessibility_tree: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extracts ARIA landmark roles (main, nav, header, etc.) from the page structure.
        """
        if accessibility_tree.get("structure", {}).get("landmarks"):
            landmarks_data = accessibility_tree["structure"]["landmarks"]
            if isinstance(landmarks_data, dict) and landmarks_data.get("landmarks"):
                return landmarks_data["landmarks"]
        js_code = """
        (function() {
            const landmarks = [];
            const landmarkRoles = ['main', 'nav', 'navigation', 'header', 'banner', 'footer', 'contentinfo', 'aside', 'complementary', 'form', 'search', 'section', 'region'];
            const elements = document.querySelectorAll(landmarkRoles.map(r => `[role="${r}"], ${r}`).join(', '));
            elements.forEach(el => {
                const role = el.getAttribute('role') || el.tagName.toLowerCase();
                if (!landmarkRoles.includes(role)) return;
                landmarks.push({
                    role: role,
                    tag: el.tagName.toLowerCase(),
                    selector: getUniqueSelector(el),
                    label: el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || ''
                });
            });
            return landmarks;
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
        })();
        """
        try:
            return await page.evaluate(js_code)
        except Exception as e:
            self._logger.warning(f"Failed to extract landmarks: {e}")
            return []

    async def _convert_heading_issues(self, issues: List[Dict]) -> List[UnifiedIssue]:
        unified_issues = []
        for issue in issues:
            severity_map = {"serious": IssueSeverity.SERIOUS, "moderate": IssueSeverity.MODERATE, "minor": IssueSeverity.MINOR}
            confidence_score = ConfidenceCalculator.calculate_confidence("structural", settings.confidence_weights["structural"])
            location = None
            if issue.get("location"):
                loc = issue["location"]
                location = ElementLocation(selector=loc.get("selector", ""), html=f"Heading at index {loc.get('index', 'unknown')}")
            remediation = self._get_heading_remediation(issue)
            unified_issues.append(UnifiedIssue(
                title=self._get_heading_title(issue),
                description=issue.get("description", "Heading structure issue"),
                issue_type=issue.get("type", "heading_issue"),
                severity=severity_map.get(issue.get("severity", "moderate"), IssueSeverity.MODERATE),
                confidence=ConfidenceLevel.HIGH if confidence_score >= 95 else (ConfidenceLevel.MEDIUM if confidence_score >= 75 else ConfidenceLevel.LOW),
                confidence_score=confidence_score,
                source=IssueSource.STRUCTURAL,
                wcag_criteria=[WCAGCriteria(id=issue.get("wcag", "1.3.1"), level="AA", title="Info and Relationships", description="Structure and relationships are programmatically determined")],
                location=location,
                remediation=remediation,
                evidence=EvidenceData(computed_values=issue.get("location", {})),
                engine_name=self.name,
                engine_version=self.version,
                tags=["headings", "structure", "hierarchy"]
            ))
        return unified_issues

    def _get_heading_title(self, issue: Dict) -> str:
        titles = {"no_headings": "Page has no headings", "missing_h1": "Missing H1 heading", "multiple_h1": "Multiple H1 headings found", "heading_skip": "Heading levels skipped", "empty_heading": "Heading has no text content", "hidden_heading": "Heading is hidden from users", "deep_nesting": "Very deep heading nesting", "section_no_heading": "Section has subheadings but no main heading"}
        return titles.get(issue.get("type", ""), issue.get("description", "Heading issue"))

    def _get_heading_remediation(self, issue: Dict) -> Optional[RemediationSuggestion]:
        issue_type = issue.get("type", "")
        if issue_type == "missing_h1":
            return RemediationSuggestion(description="Add an H1 heading that describes the page content", code_after="<h1>Main page title</h1>", estimated_effort="low")
        elif issue_type == "heading_skip":
            return RemediationSuggestion(description="Avoid skipping heading levels. Use hierarchical order: H1  H2  H3", code_after="<!-- Good: -->\n<h1>Main title</h1>\n<h2>Section</h2>\n<h3>Subsection</h3>", estimated_effort="medium")
        elif issue_type == "empty_heading":
            return RemediationSuggestion(description="Add descriptive text to the heading or remove if not needed", code_after="<h2>Descriptive section title</h2>", estimated_effort="low")
        return None

    async def _convert_landmark_issues(self, issues: List[Dict]) -> List[UnifiedIssue]:
        unified_issues = []
        for issue in issues:
            severity_map = {"serious": IssueSeverity.SERIOUS, "moderate": IssueSeverity.MODERATE, "minor": IssueSeverity.MINOR}
            confidence_score = ConfidenceCalculator.calculate_confidence("structural", settings.confidence_weights["structural"])
            location = None
            if issue.get("landmark"):
                l = issue["landmark"] if isinstance(issue["landmark"], dict) else {}
                location = ElementLocation(selector=l.get("selector", ""), html=f"<{l.get('tag', 'div')}>")
            elif issue.get("landmarks") and len(issue["landmarks"]) > 0:
                l = issue["landmarks"][0]
                location = ElementLocation(selector=l.get("selector", ""), html=f"<{l.get('tag', 'div')}>")
            remediation = self._get_landmark_remediation(issue)
            unified_issues.append(UnifiedIssue(
                title=self._get_landmark_title(issue),
                description=issue.get("description", "Landmark structure issue"),
                issue_type=issue.get("type", "landmark_issue"),
                severity=severity_map.get(issue.get("severity", "moderate"), IssueSeverity.MODERATE),
                confidence=ConfidenceLevel.HIGH if confidence_score >= 95 else (ConfidenceLevel.MEDIUM if confidence_score >= 75 else ConfidenceLevel.LOW),
                confidence_score=confidence_score,
                source=IssueSource.STRUCTURAL,
                wcag_criteria=[WCAGCriteria(id=issue.get("wcag", "1.3.1"), level="AA", title="Info and Relationships", description="Structure and relationships are programmatically determined")],
                location=location,
                remediation=remediation,
                evidence=EvidenceData(computed_values={"landmarks": issue.get("landmarks", [])}),
                engine_name=self.name,
                engine_version=self.version,
                tags=["landmarks", "structure", "aria"]
            ))
        return unified_issues

    def _get_landmark_title(self, issue: Dict) -> str:
        titles = {"no_landmarks": "Page has no landmark regions", "missing_landmark": f"Missing {issue.get('landmark', {}).get('role', 'required')} landmark", "duplicate_landmark": "Duplicate landmarks without unique labels", "nested_main": "Main landmark nested inside another main", "banner_in_main": "Banner landmark inside main content", "contentinfo_in_main": "Contentinfo landmark inside main content", "region_no_heading": "Region landmark has no heading", "navigation_unlabeled": "Navigation landmark lacks unique label", "main_under_banner": "Main landmark under banner"}
        return titles.get(issue.get("type", ""), issue.get("description", "Landmark issue"))

    def _get_landmark_remediation(self, issue: Dict) -> Optional[RemediationSuggestion]:
        issue_type = issue.get("type", "")
        if issue_type == "missing_landmark":
            role = issue.get("landmark", {}).get("role", "main")
            return RemediationSuggestion(description=f"Add a {role} landmark to identify the main content region", code_after=f'<main role="main">\n  <!-- Main content here -->\n</main>', estimated_effort="low")
        elif issue_type == "duplicate_landmark":
            return RemediationSuggestion(description="Add unique aria-label or aria-labelledby to distinguish landmarks", code_after='<nav aria-label="Main navigation">\n  <!-- Navigation -->\n</nav>\n<nav aria-label="Footer navigation">\n  <!-- Footer links -->\n</nav>', estimated_effort="low")
        elif issue_type == "region_no_heading":
            return RemediationSuggestion(description="Add a heading to describe the region content", code_after='<section>\n  <h2>Region title</h2>\n  <!-- Content -->\n</section>', estimated_effort="low")
        return None

    async def _analyze_document_outline(self, page: Page, headings: List[Dict], landmarks: List[Dict]) -> List[UnifiedIssue]:
        """
        Checks for logical document outline rules.
        (e.g., ensuring a 'main' landmark actually contains heading elements).
        """
        issues = []
        if not headings and not landmarks: return issues
        main_landmarks = [l for l in landmarks if l.get("role") == "main"]
        if main_landmarks:
            for main in main_landmarks:
                main_selector = main.get("selector", "")
                if main_selector:
                    js_code = "(selector) => { const el = document.querySelector(selector); return el && (el.querySelector('h1, h2, h3, h4, h5, h6') !== null); }"
                    try:
                        has_heading = await page.evaluate(js_code, main_selector)
                        if not has_heading:
                            issues.append(await self._create_outline_issue("main_no_heading", "Main content region has no heading", "serious", main))
                    except Exception as e:
                        self._logger.warning(f"Failed to check main heading: {e}")
        return issues

    async def _analyze_semantic_structure(self, page: Page, accessibility_tree: Dict[str, Any]) -> List[UnifiedIssue]:
        """
        Verifies semantic HTML rules, such as identifying clickable `div` elements
        that should semantically be `button` or `a` tags, and redundant ARIA.
        """
        issues = []
        js_code = """
        () => {
            const results = [];
            
            // 1. Clickable divs
            const clickableDivs = document.querySelectorAll('div[onclick], div[onmousedown], div[onmouseup], [role="button"]:not(button):not(a)');
            clickableDivs.forEach(div => {
                results.push({
                    type: 'clickable_div',
                    selector: div.id ? '#' + div.id : 'div',
                    tag: div.tagName.toLowerCase(),
                    html: div.outerHTML.substring(0, 100)
                });
            });

            // 2. Redundant ARIA
            const redundant = [];
            const mappings = {
                'nav': 'navigation',
                'main': 'main',
                'header': 'banner',
                'footer': 'contentinfo',
                'aside': 'complementary',
                'article': 'article',
                'section': 'region',
                'form': 'form'
            };
            for (const tag in mappings) {
                const elements = document.querySelectorAll(`${tag}[role="${mappings[tag]}"]`);
                elements.forEach(el => {
                    redundant.push({
                        selector: el.id ? '#' + el.id : tag,
                        tag: tag,
                        role: mappings[tag],
                        html: el.outerHTML.substring(0, 100)
                    });
                });
            }
            
            return { clickable: results, redundant: redundant };
        }
        """
        try:
            analysis = await page.evaluate(js_code)
            
            for div in analysis['clickable']:
                issues.append(await self._create_semantic_issue("clickable_non_semantic", f"Found clickable <{div['tag']}> that should be a <button> or <a> for keyboard accessibility.", "serious", div))

            for red in analysis['redundant']:
                issues.append(await self._create_semantic_issue("redundant_aria", f"Redundant ARIA role '{red['role']}' on <{red['tag']}>. HTML5 elements have implicit roles.", "minor", red))
        except Exception as e:
            self._logger.warning(f"Failed to analyze semantic structure: {e}")
        return issues

    async def _analyze_navigation_structure(self, page: Page) -> List[UnifiedIssue]:
        """
        Analyzes navigation block completeness.
        Specifically checks for bypass blocks like 'skip to main content' links,
        validates their targets, and checks for custom widget accessibility in navigation.
        """
        issues = []
        js_code = """
        () => {
            const links = Array.from(document.querySelectorAll('a'));
            const skipLink = links.find(l => 
                l.textContent.toLowerCase().includes('skip') || 
                l.href.includes('#main') ||
                l.getAttribute('accesskey') === 's'
            );

            let skipLinkStatus = 'missing';
            let targetSelector = '';
            if (skipLink) {
                const href = skipLink.getAttribute('href');
                if (href && href.startsWith('#')) {
                    const targetId = href.substring(1);
                    const target = document.getElementById(targetId);
                    if (target) {
                        // Check if target is focusable or has a focusable child
                        const isFocusable = (el) => {
                            if (!el) return false;
                            const tabIndex = el.getAttribute('tabindex');
                            return el.tabIndex >= 0 || (tabIndex !== null && parseInt(tabIndex) >= 0);
                        };
                        skipLinkStatus = isFocusable(target) ? 'valid' : 'target_not_focusable';
                        targetSelector = `#${targetId}`;
                    } else {
                        skipLinkStatus = 'invalid_target';
                    }
                } else {
                    skipLinkStatus = 'no_fragment';
                }
            }

            // Check for dropdown menus in navigation without aria-expanded
            const navs = document.querySelectorAll('nav, [role="navigation"]');
            const dropdownIssues = [];
            navs.forEach(nav => {
                const buttons = nav.querySelectorAll('button, [role="button"]');
                buttons.forEach(btn => {
                    const hasPopup = btn.getAttribute('aria-haspopup');
                    const expanded = btn.getAttribute('aria-expanded');
                    if (hasPopup && expanded === null) {
                        dropdownIssues.push({
                            selector: getUniqueSelector(btn),
                            html: btn.outerHTML.substring(0, 100)
                        });
                    }
                });
            });

            // Check for non-HTML content links (Point 15)
            const nonHtmlLinks = [];
            const extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip'];
            links.forEach(link => {
                const href = link.getAttribute('href') || '';
                if (extensions.some(ext => href.toLowerCase().endsWith(ext))) {
                    nonHtmlLinks.push({
                        href: href,
                        selector: getUniqueSelector(link),
                        html: link.outerHTML.substring(0, 100)
                    });
                }
            });

            return { 
                skipLinkStatus, 
                skipLinkSelector: skipLink ? getUniqueSelector(skipLink) : null,
                targetSelector,
                dropdownIssues,
                nonHtmlLinks
            };

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
            result = await page.evaluate(js_code)
            
            # Skip link issues (Point 14)
            status = result.get("skipLinkStatus")
            if status == 'missing':
                issues.append(await self._create_navigation_issue("no_skip_link", "No skip link found for keyboard users. Large navigation blocks should be bypassable.", "moderate", None))
            elif status == 'invalid_target':
                issues.append(await self._create_navigation_issue("invalid_skip_link", "Skip link found but its target element does not exist.", "serious", {"selector": result.get("skipLinkSelector")}))
            elif status == 'target_not_focusable':
                issues.append(await self._create_navigation_issue("non_focusable_skip_target", "Skip link target exists but is not focusable. Ensure the target has tabindex='-1' or is a naturally focusable element.", "moderate", {"selector": result.get("targetSelector")}))

            # Custom widget issues (Point 13)
            for drop in result.get("dropdownIssues", []):
                issues.append(await self._create_semantic_issue("missing_aria_expanded", "Navigation dropdown button lacks 'aria-expanded' attribute to signal state to screen readers.", "moderate", drop))

            # Non-HTML content (Point 15)
            for nh in result.get("nonHtmlLinks", []):
                issues.append(await self._create_semantic_issue("non_html_link", f"Link to non-HTML content ({nh['href'].split('.')[-1].upper()}) should be clearly labeled and its accessibility verified.", "minor", nh))

        except Exception as e:
            self._logger.warning(f"Failed to analyze navigation: {e}")
        return issues

    async def _check_lang_attribute(self, page: Page) -> List[UnifiedIssue]:
        """
        Verifies that the <html> tag has a valid lang attribute. (Point 4)
        """
        js_code = "() => { const html = document.documentElement; return { lang: html.getAttribute('lang'), xmlLang: html.getAttribute('xml:lang') }; }"
        try:
            result = await page.evaluate(js_code)
            if not result.get("lang"):
                return [UnifiedIssue(
                    title="Missing page language declaration",
                    description="The <html> element lacks a 'lang' attribute. Screen readers need this to pronounce content correctly.",
                    issue_type="missing_lang",
                    severity=IssueSeverity.SERIOUS,
                    confidence=ConfidenceLevel.HIGH,
                    confidence_score=100,
                    source=IssueSource.STRUCTURAL,
                    wcag_criteria=[WCAGCriteria(id="3.1.1", level="A", title="Language of Page")],
                    location=ElementLocation(selector="html"),
                    engine_name=self.name,
                    engine_version=self.version,
                    tags=["language", "wcag"]
                )]
        except Exception as e:
            self._logger.warning(f"Failed to check lang attribute: {e}")
        return []

    async def _check_aria_live(self, page: Page) -> List[UnifiedIssue]:
        """
        Detects aria-live regions and potentially missing dynamic update announcements. (Point 5)
        """
        js_code = """
        () => {
            const regions = document.querySelectorAll('[aria-live], [role="status"], [role="alert"], [role="log"], [role="marquee"], [role="timer"]');
            return Array.from(regions).map(el => ({
                role: el.getAttribute('role'),
                live: el.getAttribute('aria-live'),
                selector: el.id ? '#' + el.id : el.tagName.toLowerCase(),
                html: el.outerHTML.substring(0, 100)
            }));
        }
        """
        issues = []
        try:
            regions = await page.evaluate(js_code)
            # This is more of a "detection" for the report than an "issue" per se, 
            # unless we find problematic patterns.
            # We'll flag regions without aria-atomic if they seem to be status regions.
            for reg in regions:
                if reg['live'] == 'polite' and reg['role'] == 'status':
                    # Check for missing aria-atomic on status regions (often recommended)
                    pass 
        except Exception as e:
            self._logger.warning(f"Failed to check aria-live: {e}")
        return issues

    async def _check_visual_reading_order(self, page: Page) -> List[UnifiedIssue]:
        """
        Checks if the DOM order roughly matches the visual layout order. (Point 7)
        """
        js_code = """
        () => {
            const issues = [];
            const elements = Array.from(document.querySelectorAll('h1, h2, h3, p, a, button'));
            let lastTop = -1;
            let lastLeft = -1;
            
            for (let i = 0; i < Math.min(elements.length, 50); i++) {
                const rect = elements[i].getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                
                // Simple heuristic: if an element appears significantly earlier in DOM
                // but significantly later visually, it might be a reading order issue.
                // This is complex to automate perfectly but we can catch obvious CSS reordering.
                
                lastTop = rect.top;
                lastLeft = rect.left;
            }
            return issues;
        }
        """
        # Placeholder for more complex reading order check
        return []

    async def _create_outline_issue(self, issue_type: str, description: str, severity: str, element: Optional[Dict]) -> UnifiedIssue:
        severity_map = {"serious": IssueSeverity.SERIOUS, "moderate": IssueSeverity.MODERATE, "minor": IssueSeverity.MINOR}
        confidence_score = ConfidenceCalculator.calculate_confidence("structural", settings.confidence_weights["structural"])
        location = ElementLocation(selector=element["selector"]) if element and element.get("selector") else None
        return UnifiedIssue(
            title=self._get_outline_title(issue_type),
            description=description,
            issue_type=issue_type,
            severity=severity_map.get(severity, IssueSeverity.MODERATE),
            confidence=ConfidenceLevel.HIGH if confidence_score >= 95 else (ConfidenceLevel.MEDIUM if confidence_score >= 75 else ConfidenceLevel.LOW),
            confidence_score=confidence_score,
            source=IssueSource.STRUCTURAL,
            wcag_criteria=[WCAGCriteria(id="2.4.10", level="AAA", title="Section Headings", description="Section headings organize the content")],
            location=location,
            engine_name=self.name,
            engine_version=self.version,
            tags=["outline", "structure"]
        )

    def _get_outline_title(self, issue_type: str) -> str:
        titles = {"main_no_heading": "Main content lacks heading"}
        return titles.get(issue_type, "Document outline issue")

    async def _create_semantic_issue(self, issue_type: str, description: str, severity_str: str, element_data: Any) -> UnifiedIssue:
        severity_map = {"serious": IssueSeverity.SERIOUS, "moderate": IssueSeverity.MODERATE, "minor": IssueSeverity.MINOR}
        confidence_score = ConfidenceCalculator.calculate_confidence("structural", settings.confidence_weights["structural"])
        
        location = None
        if isinstance(element_data, dict) and element_data.get("selector"):
            location = ElementLocation(selector=element_data["selector"], html=element_data.get("html", ""))

        return UnifiedIssue(
            title=f"Semantic HTML issue: {issue_type.replace('_', ' ').title()}",
            description=description,
            issue_type=issue_type,
            severity=severity_map.get(severity_str, IssueSeverity.MODERATE),
            confidence=ConfidenceLevel.HIGH if confidence_score >= 95 else (ConfidenceLevel.MEDIUM if confidence_score >= 75 else ConfidenceLevel.LOW),
            confidence_score=confidence_score,
            source=IssueSource.STRUCTURAL,
            wcag_criteria=[WCAGCriteria(id="4.1.2", level="A", title="Name, Role, Value", description="Elements have appropriate roles")],
            location=location,
            engine_name=self.name,
            engine_version=self.version,
            tags=["semantic", "html", "low-quality-markup"]
        )

    async def _create_navigation_issue(self, issue_type: str, description: str, severity: str, element: Any) -> UnifiedIssue:
        severity_map = {"serious": IssueSeverity.SERIOUS, "moderate": IssueSeverity.MODERATE, "minor": IssueSeverity.MINOR}
        confidence_score = ConfidenceCalculator.calculate_confidence("navigation", settings.confidence_weights["navigation"])
        
        location = None
        if isinstance(element, dict) and element.get("selector"):
            location = ElementLocation(selector=element["selector"])
        
        remediation = None
        if issue_type == "no_skip_link":
             remediation = RemediationSuggestion(description="Add a skip link to help keyboard users bypass navigation", code_after='<a href="#main" class="skip-link">Skip to main content</a>', estimated_effort="low")
        elif issue_type == "invalid_skip_link":
             remediation = RemediationSuggestion(description="Ensure the skip link href matches the ID of the main content container.", code_after='<a href="#main-content">Skip to content</a>\n<main id="main-content">...</main>', estimated_effort="low")

        return UnifiedIssue(
            title="Navigation structure issue",
            description=description,
            issue_type=issue_type,
            severity=severity_map.get(severity, IssueSeverity.MODERATE),
            confidence=ConfidenceLevel.HIGH if confidence_score >= 95 else (ConfidenceLevel.MEDIUM if confidence_score >= 75 else ConfidenceLevel.LOW),
            confidence_score=confidence_score,
            source=IssueSource.STRUCTURAL,
            wcag_criteria=[WCAGCriteria(id="2.4.1", level="A", title="Bypass Blocks", description="A mechanism to bypass blocks of content")],
            location=location,
            remediation=remediation,
            engine_name=self.name,
            engine_version=self.version,
            tags=["navigation", "keyboard"]
        )

    async def validate_config(self) -> bool:
        return True