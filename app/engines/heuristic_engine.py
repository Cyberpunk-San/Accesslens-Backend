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

class HeuristicEngine(BaseAccessibilityEngine):
    """
    Heuristic-based auditing for UX patterns that automated tools often miss.
    Focuses on link quality, density, and cognitive load indicators.
    """

    REPETITIVE_TEXTS = ["click here", "read more", "more", "here", "link", "go"]

    def __init__(self):
        super().__init__("heuristic", "1.0.0")
        self.capabilities = ["heuristic", "ux", "cognitive"]

    async def analyze(
        self,
        page_data: Dict[str, Any],
        request: AuditRequest
    ) -> List[UnifiedIssue]:
        page = page_data.get("page")
        if not page:
            return []

        issues = []
        
        # 1. Tech Stack Detection (for specific remediation)
        stack_issues = await self._detect_tech_stack(page)
        issues.extend(stack_issues)

        # 2. Link Text Descriptiveness
        link_issues = await self._check_link_descriptiveness(page)
        issues.extend(link_issues)
        
        # 3. Element Density & Touch Target Size
        density_issues = await self._check_element_density(page)
        issues.extend(density_issues)
        target_issues = await self._check_touch_target_size(page)
        issues.extend(target_issues)
        
        # 4. Redundant Titles Check
        redundant_issues = await self._check_redundant_titles(page)
        issues.extend(redundant_issues)
        
        # 5. Cognitive Reading Complexity Check
        cognitive_issues = await self._check_reading_complexity(page)
        issues.extend(cognitive_issues)

        # 6. Animation & Motion Sensitivity
        motion_issues = await self._check_animations(page)
        issues.extend(motion_issues)

        # 7. Text Resizing & Zoom
        zoom_issues = await self._check_layout_flexibility(page)
        issues.extend(zoom_issues)

        # 8. Timeouts
        timeout_issues = await self._check_timeouts(page)
        issues.extend(timeout_issues)
        
        # 9. False Perfection Detection (Integrity Check)
        # We run this last to see if other issues were found
        false_perfection = await self._check_false_perfection(page, issues)
        issues.extend(false_perfection)

        return issues

    async def _check_link_descriptiveness(self, page: Any) -> List[UnifiedIssue]:
        """Detects links with generic, non-descriptive text like 'Click here'."""
        script = """
        () => {
            const results = [];
            const links = Array.from(document.querySelectorAll('a'));
            const GENERIC = ['click here', 'read more', 'more', 'here', 'link', 'go', 'view', 'continue', 'learn more'];
            
            const textCounts = {};
            links.forEach(link => {
                const text = link.innerText.trim().toLowerCase();
                if (text) {
                    textCounts[text] = textCounts[text] || [];
                    textCounts[text].push(link);
                }
            });
            
            links.forEach(link => {
                const text = link.innerText.trim().toLowerCase();
                if (GENERIC.includes(text)) {
                    results.push({
                        type: 'vague_link',
                        text: text,
                        count: textCounts[text] ? textCounts[text].length : 1,
                        selector: getUniqueSelector(link),
                        html: link.outerHTML.substring(0, 100)
                    });
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
            seen_selectors = set()
            for f in findings:
                if f['selector'] in seen_selectors: continue
                seen_selectors.add(f['selector'])
                
                title = f"Non-descriptive link text: '{f['text']}'"
                description = f"The link text '{f['text']}' does not describe the destination or purpose of the link."
                if f['count'] > 1:
                    description += f" This generic text is used {f['count']} times on the page, making it difficult for screen reader users to distinguish between links."
                
                issues.append(UnifiedIssue(
                    title=title,
                    description=description,
                    issue_type="VAGUE_LINK_TEXT",
                    severity=IssueSeverity.MODERATE,
                    confidence=ConfidenceLevel.HIGH,
                    confidence_score=95.0,
                    source=IssueSource.HEURISTIC,
                    wcag_criteria=[WCAGCriteria(id="2.4.4", level="A", title="Link Purpose (In Context)")],
                    location=ElementLocation(selector=f['selector'], html=f['html']),
                    remediation=RemediationSuggestion(
                        description="Replace generic link text with descriptive text (e.g., 'Read the DRDO internship guide' instead of 'Read more').",
                        estimated_fix_hours=0.5,
                        verification_steps=[
                            "Check if the link text alone conveys the destination",
                            "Ensure the link makes sense when read out of context by a screen reader"
                        ]
                    ),
                    engine_name=self.name,
                    engine_version=self.version
                ))
            return issues
        except Exception as e:
            logger.error(f"Link descriptiveness check failed: {e}")
            return []

    async def _check_touch_target_size(self, page: Any) -> List[UnifiedIssue]:
        """Detects interactive elements with small touch targets (Point 6)."""
        script = """
        () => {
            const results = [];
            const interactive = document.querySelectorAll('a, button, input, select, [role="button"]');
            interactive.forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;
                
                if (rect.width < 44 || rect.height < 44) {
                    results.push({
                        selector: el.id ? '#' + el.id : el.tagName.toLowerCase(),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                        html: el.outerHTML.substring(0, 100)
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
                    title="Small touch target size",
                    description=f"Interactive element is {f['width']}x{f['height']}px, which is smaller than the recommended minimum of 44x44px. This can be difficult for users with motor impairments or those using touch screens.",
                    issue_type="TOUCH_TARGET_SIZE",
                    severity=IssueSeverity.MODERATE,
                    confidence=ConfidenceLevel.HIGH,
                    confidence_score=98.0,
                    source=IssueSource.HEURISTIC,
                    wcag_criteria=[WCAGCriteria(id="2.5.5", level="AAA", title="Target Size")],
                    location=ElementLocation(selector=f['selector'], html=f['html']),
                    remediation=RemediationSuggestion(
                        description="Increase the size of the element or its padding to meet the 44x44px requirement.",
                        estimated_effort="Low"
                    ),
                    engine_name=self.name,
                    engine_version=self.version
                ))
            return issues
        except Exception as e:
            logger.error(f"Touch target check failed: {e}")
            return []

    async def _check_animations(self, page: Any) -> List[UnifiedIssue]:
        """Detects potential animation issues (Point 9)."""
        script = """
        () => {
            const results = [];
            const videos = document.querySelectorAll('video[autoplay]');
            videos.forEach(v => {
                results.push({
                    type: 'autoplay_video',
                    selector: 'video',
                    html: v.outerHTML.substring(0, 100)
                });
            });
            
            // Check for large CSS animations (heuristic)
            const allElements = document.querySelectorAll('*');
            allElements.forEach(el => {
                const style = window.getComputedStyle(el);
                if (style.animationIterationCount === 'infinite' || parseFloat(style.animationDuration) > 5) {
                    results.push({
                        type: 'long_animation',
                        selector: el.tagName.toLowerCase(),
                        html: el.outerHTML.substring(0, 100)
                    });
                }
            });
            return results;
        }
        """
        try:
            findings = await page.evaluate(script)
            issues = []
            seen_selectors = set()
            for f in findings:
                if f['selector'] in seen_selectors: continue
                seen_selectors.add(f['selector'])
                issues.append(UnifiedIssue(
                    title="Motion or animation detected",
                    description="Auto-playing animations or long-running motion can trigger vestibular disorders or distract users. Ensure users can pause, stop, or hide them.",
                    issue_type="ANIMATION_CHECK",
                    severity=IssueSeverity.MINOR,
                    confidence=ConfidenceLevel.MEDIUM,
                    confidence_score=70.0,
                    source=IssueSource.HEURISTIC,
                    wcag_criteria=[WCAGCriteria(id="2.2.2", level="A", title="Pause, Stop, Hide")],
                    location=ElementLocation(selector=f['selector'], html=f['html']),
                    remediation=RemediationSuggestion(
                        description="Provide controls to pause animations or respect the 'prefers-reduced-motion' media query.",
                        estimated_effort="Medium"
                    ),
                    engine_name=self.name,
                    engine_version=self.version
                ))
            return issues
        except Exception as e:
            logger.error(f"Animation check failed: {e}")
            return []

    async def _check_layout_flexibility(self, page: Any) -> List[UnifiedIssue]:
        """Checks for layout issues when text is resized (Point 11)."""
        script = """
        () => {
            const results = [];
            const elements = document.querySelectorAll('*');
            elements.forEach(el => {
                const style = window.getComputedStyle(el);
                if (style.overflow === 'hidden' && (style.height !== 'auto' || style.maxHeight !== 'none')) {
                    // Potential text clipping issue on zoom
                    if (el.innerText.length > 50) {
                        results.push({
                            selector: el.tagName.toLowerCase(),
                            html: el.outerHTML.substring(0, 100)
                        });
                    }
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
                    title="Potential text clipping on zoom",
                    description="Element has fixed height and overflow: hidden. This can cause text to be clipped when users increase text size or zoom in.",
                    issue_type="ZOOM_CHECK",
                    severity=IssueSeverity.MINOR,
                    confidence=ConfidenceLevel.LOW,
                    confidence_score=50.0,
                    source=IssueSource.HEURISTIC,
                    wcag_criteria=[WCAGCriteria(id="1.4.4", level="AA", title="Resize Text")],
                    location=ElementLocation(selector=f['selector'], html=f['html']),
                    remediation=RemediationSuggestion(
                        description="Use min-height instead of fixed height and ensure containers can expand to accommodate larger text.",
                        estimated_effort="Medium"
                    ),
                    engine_name=self.name,
                    engine_version=self.version
                ))
            return issues
        except Exception as e:
            logger.error(f"Layout flexibility check failed: {e}")
            return []

    async def _check_timeouts(self, page: Any) -> List[UnifiedIssue]:
        """Checks for potential session timeouts (Point 12)."""
        script = """
        () => {
            const results = [];
            const meta = document.querySelector('meta[http-equiv="refresh"]');
            if (meta) {
                results.push({
                    selector: 'meta',
                    html: meta.outerHTML
                });
            }
            return results;
        }
        """
        try:
            findings = await page.evaluate(script)
            issues = []
            for f in findings:
                issues.append(UnifiedIssue(
                    title="Auto-refresh or timeout detected",
                    description="The page uses a meta refresh tag, which can disorient users or timeout sessions unexpectedly. WCAG recommends against auto-refreshing pages without user control.",
                    issue_type="TIMEOUT_CHECK",
                    severity=IssueSeverity.MODERATE,
                    confidence=ConfidenceLevel.HIGH,
                    confidence_score=100.0,
                    source=IssueSource.HEURISTIC,
                    wcag_criteria=[WCAGCriteria(id="2.2.1", level="A", title="Timing Adjustable")],
                    location=ElementLocation(selector=f['selector'], html=f['html']),
                    remediation=RemediationSuggestion(
                        description="Remove meta refresh or provide a way for users to extend the timeout.",
                        estimated_effort="Medium"
                    ),
                    engine_name=self.name,
                    engine_version=self.version
                ))
            return issues
        except Exception as e:
            logger.error(f"Timeout check failed: {e}")
            return []

    async def _check_element_density(self, page: Any) -> List[UnifiedIssue]:
        """Detects clusters of small, closely-packed interactive elements."""
        script = """
        () => {
            const results = [];
            const interactive = Array.from(document.querySelectorAll('a, button, input, select, [role="button"]'));
            
            for (let i = 0; i < interactive.length; i++) {
                const el1 = interactive[i];
                const rect1 = el1.getBoundingClientRect();
                
                if (rect1.width === 0 || rect1.height === 0) continue;
                
                let neighbors = 0;
                for (let j = 0; j < interactive.length; j++) {
                    if (i === j) continue;
                    const el2 = interactive[j];
                    const rect2 = el2.getBoundingClientRect();
                    
                    const dist = Math.sqrt(
                        Math.pow(rect1.left - rect2.left, 2) + 
                        Math.pow(rect1.top - rect2.top, 2)
                    );
                    
                    if (dist < 40) neighbors++;
                }
                
                if (neighbors > 5) {
                    results.push({
                        selector: el1.id ? '#' + el1.id : el1.tagName.toLowerCase(),
                        count: neighbors,
                        html: el1.outerHTML.substring(0, 100)
                    });
                    // Skip next few to avoid spamming the same cluster
                    i += 3;
                }
            }
            return results;
        }
        """
        try:
            findings = await page.evaluate(script)
            issues = []
            for f in findings:
                issues.append(UnifiedIssue(
                    title="High interactive element density",
                    description=f"This element is part of a cluster with {f['count']} interactive items in close proximity. This can cause cognitive overload and makes it difficult for users with motor impairments to target specific elements.",
                    issue_type="UX_HEURISTIC",
                    severity=IssueSeverity.MINOR,
                    confidence=ConfidenceLevel.MEDIUM,
                    confidence_score=75.0,
                    source=IssueSource.HEURISTIC,
                    location=ElementLocation(selector=f['selector'], html=f['html']),
                    remediation=RemediationSuggestion(
                        description="Increase spacing between interactive elements or group related functions into clear, labeled regions to reduce visual noise.",
                        estimated_effort="Medium"
                    ),
                    engine_name=self.name,
                    engine_version=self.version
                ))
            return issues
        except Exception as e:
            logger.error(f"Density check failed: {e}")
            return []

    async def _check_redundant_titles(self, page: Any) -> List[UnifiedIssue]:
        """Flags links where title attribute is identical to the link text."""
        script = """
        () => {
            const results = [];
            const links = Array.from(document.querySelectorAll('a[title]'));
            
            links.forEach(link => {
                const text = link.innerText.trim();
                const title = link.getAttribute('title').trim();
                
                if (text && title && text === title) {
                    results.push({
                        selector: link.id ? '#' + link.id : 'a',
                        text: text,
                        html: link.outerHTML.substring(0, 100)
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
                    title="Redundant title attribute on link",
                    description=f"The title attribute '{f['text']}' is identical to the link text. This creates redundant announcements for screen reader users.",
                    issue_type="UX_HEURISTIC",
                    severity=IssueSeverity.MINOR,
                    confidence=ConfidenceLevel.HIGH,
                    confidence_score=98.0,
                    source=IssueSource.HEURISTIC,
                    location=ElementLocation(selector=f['selector'], html=f['html']),
                    remediation=RemediationSuggestion(
                        description="Remove the title attribute if it matches the link text exactly. Title attributes should only be used to provide additional, non-essential information.",
                        estimated_effort="Low"
                    ),
                    engine_name=self.name,
                    engine_version=self.version
                ))
            return issues
        except Exception as e:
            logger.error(f"Redundant titles check failed: {e}")
            return []

    async def _check_reading_complexity(self, page: Any) -> List[UnifiedIssue]:
        """
        Calculates the Flesch-Kincaid Reading Ease score for visible page text.
        FK Score < 60 = Difficult (university level). < 30 = Very difficult.
        WCAG 3.1.5 (AAA) recommends content be readable at a lower secondary level (FK ~60+).
        """
        script = """
        () => {
            // Collect visible text only — skip script, style, aria-hidden elements
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                {
                    acceptNode(node) {
                        const p = node.parentElement;
                        if (!p) return NodeFilter.FILTER_REJECT;
                        const tag = p.tagName.toUpperCase();
                        if (['SCRIPT','STYLE','NOSCRIPT','TEMPLATE'].includes(tag)) return NodeFilter.FILTER_REJECT;
                        if (p.getAttribute('aria-hidden') === 'true') return NodeFilter.FILTER_REJECT;
                        const s = window.getComputedStyle(p);
                        if (s.display === 'none' || s.visibility === 'hidden') return NodeFilter.FILTER_REJECT;
                        return NodeFilter.FILTER_ACCEPT;
                    }
                }
            );
            let text = '';
            let node;
            while ((node = walker.nextNode())) text += ' ' + node.textContent;
            text = text.trim();

            // Need at least 100 words for a meaningful score
            const words = text.split(/\\s+/).filter(w => w.length > 0);
            if (words.length < 100) return null;

            // Count sentences (split on . ! ? followed by whitespace or end)
            const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 3);
            if (sentences.length < 2) return null;

            // Count syllables (approximation: count vowel groups per word)
            function countSyllables(word) {
                word = word.toLowerCase().replace(/[^a-z]/g, '');
                if (word.length <= 3) return 1;
                word = word.replace(/e$/, '');
                const m = word.match(/[aeiouy]+/g);
                return m ? m.length : 1;
            }

            const totalSyllables = words.reduce((acc, w) => acc + countSyllables(w), 0);
            const avgWordsPerSentence = words.length / sentences.length;
            const avgSyllablesPerWord = totalSyllables / words.length;

            // Flesch-Kincaid Reading Ease
            const fkScore = 206.835
                - (1.015  * avgWordsPerSentence)
                - (84.6   * avgSyllablesPerWord);

            return {
                fkScore: Math.round(fkScore * 10) / 10,
                avgWordsPerSentence: Math.round(avgWordsPerSentence),
                avgSyllablesPerWord: Math.round(avgSyllablesPerWord * 10) / 10,
                wordCount: words.length
            };
        }
        """
        try:
            finding = await page.evaluate(script)
            if not finding:
                return []

            fk = finding['fkScore']

            # Only flag if difficult (FK < 60) or very difficult (FK < 30)
            if fk >= 60:
                return []

            severity = IssueSeverity.SERIOUS if fk < 30 else IssueSeverity.MINOR
            confidence_level = ConfidenceLevel.MEDIUM if fk < 30 else ConfidenceLevel.LOW
            confidence_score = 80.0 if fk < 30 else 65.0
            level_desc = "very difficult" if fk < 30 else "difficult"

            return [UnifiedIssue(
                title=f"High reading complexity (Flesch-Kincaid score: {fk})",
                description=(
                    f"The page content has a Flesch-Kincaid Reading Ease score of {fk}, "
                    f"indicating {level_desc} text (avg {finding['avgWordsPerSentence']} words/sentence, "
                    f"{finding['avgSyllablesPerWord']} syllables/word across {finding['wordCount']} words). "
                    "Scores below 60 are hard for most adults; below 30 requires a university degree level. "
                    "WCAG 3.1.5 recommends content readable at lower secondary school level (score ~60+)."
                ),
                issue_type="COGNITIVE_COMPLEXITY",
                severity=severity,
                confidence=confidence_level,
                confidence_score=confidence_score,
                source=IssueSource.HEURISTIC,
                wcag_criteria=[WCAGCriteria(
                    id="3.1.5", level="AAA",
                    title="Reading Level",
                    description="Where text requires reading ability more advanced than lower secondary education level, supplemental content or a simpler version is available."
                )],
                location=ElementLocation(selector="body", html="Entire page text"),
                remediation=RemediationSuggestion(
                    description=(
                        "Simplify language: use shorter sentences (target < 20 words), "
                        "prefer common words, break up dense paragraphs with headings and "
                        "bullet lists. Aim for a Flesch-Kincaid score of 60 or above."
                    ),
                    estimated_effort="High"
                ),
                engine_name=self.name,
                engine_version=self.version
            )]
        except Exception as e:
            logger.error(f"Reading complexity check failed: {e}")
            return []

    async def _detect_tech_stack(self, page: Any) -> List[UnifiedIssue]:
        """Detects CMS/Framework to provide specific remediation paths."""
        script = """
        () => {
            const stack = [];
            const generator = document.querySelector('meta[name="generator"]');
            const genContent = generator ? generator.getAttribute("content") : "";
            
            if (genContent.includes("Drupal") || window.Drupal) stack.push("Drupal");
            if (genContent.includes("WordPress") || document.querySelector('link[href*="wp-content"]')) stack.push("WordPress");
            if (window._spPageContextInfo) stack.push("SharePoint");
            
            return stack;
        }
        """
        try:
            detected = await page.evaluate(script)
            if not detected: return []
            
            # This isn't an "issue", but a diagnostic to help the user.
            # We record it as an INFO level issue or just return empty for now
            # but we'll use it to inject advice into other issues eventually.
            # For now, let's just return a placeholder so we know it's working.
            return [] 
        except Exception:
            return []

    async def _check_false_perfection(self, page: Any, issues: List[UnifiedIssue]) -> List[UnifiedIssue]:
        """Flags reports that might be 'too clean' to be true on complex pages."""
        if len(issues) > 2: return [] # Probably okay
        
        script = """
        () => {
            return {
                nodeCount: document.querySelectorAll('*').length,
                scrollHeight: document.documentElement.scrollHeight,
                textLength: document.body.innerText.length
            };
        }
        """
        try:
            stats = await page.evaluate(script)
            if stats['nodeCount'] > 800 and stats['textLength'] > 2000:
                return [UnifiedIssue(
                    title="Audit Integrity: Suspiciously high score detected",
                    description=(
                        f"This page has {stats['nodeCount']} elements and {stats['textLength']} characters of text, "
                        "but the automated audit found very few issues. This can occur if the content is "
                        "dynamic (JS-heavy) and was not fully rendered, or if it uses non-standard components."
                    ),
                    issue_type="AUDIT_INTEGRITY",
                    severity=IssueSeverity.MINOR,
                    confidence=ConfidenceLevel.LOW,
                    confidence_score=60.0,
                    source=IssueSource.HEURISTIC,
                    location=ElementLocation(selector="body", html="Page stats check"),
                    remediation=RemediationSuggestion(
                        description="Perform a manual verification using a Screen Reader or Tab-traversal to ensure the automated engines didn't miss dynamic content.",
                        estimated_fix_hours=1.0,
                        verification_steps=["Manual Tab-through", "Check for generic role='presentation' usage"]
                    ),
                    engine_name=self.name,
                    engine_version=self.version
                )]
            return []
        except Exception:
            return []

    async def validate_config(self) -> bool:
        return True
