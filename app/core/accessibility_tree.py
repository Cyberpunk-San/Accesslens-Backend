
from typing import Dict, Any, List, Optional
from playwright.async_api import Page
import asyncio
import json
import logging

class AccessibilityTreeExtractor:


    def __init__(self):
        self._logger = logging.getLogger(__name__)

    async def extract(self, page: Page) -> Dict[str, Any]:

        try:

            await page.wait_for_load_state("networkidle")


            accessibility_tree = await self._get_full_accessibility_tree(page)


            computed_styles = await self._get_computed_styles(page)


            dom_snapshot = await self._get_dom_snapshot(page)


            aria_info = await self._get_aria_information(page)


            heading_structure = await self._get_heading_structure(page)


            landmarks = await self._get_landmark_regions(page)


            focusable_elements = await self._get_focusable_elements(page)

            return {
                "snapshot": {
                    "timestamp": self._get_timestamp(),
                    "url": page.url,
                    "title": await page.title()
                },
                "accessibility_tree": accessibility_tree,
                "computed_styles": computed_styles,
                "dom_snapshot": dom_snapshot,
                "aria_info": aria_info,
                "structure": {
                    "headings": heading_structure,
                    "landmarks": landmarks,
                    "focusable_elements": focusable_elements
                },
                "statistics": await self._compute_statistics(page, {
                    "headings": heading_structure,
                    "landmarks": landmarks,
                    "focusable_elements": focusable_elements
                })
            }
        except Exception as e:
            self._logger.error(f"Failed to extract accessibility tree: {e}")
            return {"error": str(e)}

    async def _get_full_accessibility_tree(self, page: Page) -> Dict[str, Any]:

        try:

            client = await page.context.new_cdp_session(page)
            await client.send("Accessibility.enable")


            result = await client.send("Accessibility.getFullAXTree")


            tree = self._normalize_accessibility_nodes(result.get("nodes", []))

            return {
                "nodes": tree,
                "node_count": len(tree)
            }
        except Exception as e:
            self._logger.warning(f"CDP accessibility tree failed: {e}")

            return await self._extract_accessibility_tree_js(page)

    async def _extract_accessibility_tree_js(self, page: Page) -> Dict[str, Any]:

        js_code = """
        (function() {
            function buildTree(element) {
                const node = {
                    role: element.getAttribute('role') || element.tagName.toLowerCase(),
                    name: element.getAttribute('aria-label') || element.innerText || '',
                    children: []
                };
                for (const child of element.children) {
                    node.children.push(buildTree(child));
                }
                return node;
            }
            return buildTree(document.body);
        })()
        """

        try:
            tree = await page.evaluate(js_code)
            return {
                "nodes": [tree],
                "node_count": self._count_nodes(tree),
                "method": "javascript_fallback"
            }
        except Exception as e:
            self._logger.error(f"JS accessibility tree failed: {e}")
            return {"nodes": [], "node_count": 0, "error": str(e)}

    def _normalize_accessibility_nodes(self, nodes: List[Dict]) -> List[Dict]:

        normalized = []

        for node in nodes:
            normalized_node = {
                "nodeId": node.get("nodeId"),
                "role": node.get("role", {}).get("value"),
                "name": node.get("name", {}).get("value"),
                "description": node.get("description", {}).get("value"),
                "value": node.get("value", {}).get("value"),
                "properties": {},
                "childIds": node.get("childIds", [])
            }


            for prop in node.get("properties", []):
                normalized_node["properties"][prop.get("name")] = prop.get("value", {}).get("value")


            if "backendDOMNodeId" in node:
                normalized_node["backendDOMNodeId"] = node["backendDOMNodeId"]

            normalized.append(normalized_node)

        return normalized

    def _count_nodes(self, node: Dict) -> int:

        count = 1
        for child in node.get("children", []):
            count += self._count_nodes(child)
        return count

    async def _get_computed_styles(self, page: Page) -> Dict[str, Any]:

        js_code = """
        () => {
            const styles = {};
            const elements = document.querySelectorAll('*');
            elements.forEach(el => {
                const computed = window.getComputedStyle(el);
                styles[el.tagName] = {
                    color: computed.color,
                    backgroundColor: computed.backgroundColor
                };
            });
            return styles;
        }
        """

        try:
            return await page.evaluate(js_code)
        except Exception as e:
            self._logger.warning(f"Failed to get computed styles: {e}")
            return {}

    async def _get_dom_snapshot(self, page: Page) -> Dict[str, Any]:

        try:
            client = await page.context.new_cdp_session(page)
            snapshot = await client.send("DOMSnapshot.captureSnapshot", {
                "computedStyles": [
                    "display",
                    "visibility",
                    "opacity"
                ]
            })
            return snapshot
        except Exception as e:
            self._logger.warning(f"DOM snapshot failed: {e}")
            return {}

    async def _get_aria_information(self, page: Page) -> Dict[str, Any]:

        js_code = """
        () => {
            return Array.from(document.querySelectorAll('*'))
                .filter(el => Array.from(el.attributes).some(attr => attr.name.startsWith('aria-')))
                .map(el => ({
                    tag: el.tagName.toLowerCase(),
                    attributes: Array.from(el.attributes)
                        .filter(attr => attr.name.startsWith('aria-'))
                        .reduce((acc, attr) => ({ ...acc, [attr.name]: attr.value }), {})
                }));
        }
        """

        try:
            return await page.evaluate(js_code)
        except Exception as e:
            self._logger.warning(f"Failed to extract ARIA info: {e}")
            return []

    async def _get_heading_structure(self, page: Page) -> List[Dict[str, Any]]:

        js_code = """
        () => {
            return Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6, [role="heading"]'))
                .map(el => ({
                    level: parseInt(el.tagName.substring(1)) || parseInt(el.getAttribute('aria-level')) || 2,
                    text: el.innerText.trim(),
                    isVisible: el.offsetParent !== null
                }));
        }
        """

        try:
            headings = await page.evaluate(js_code)


            hierarchy_issues = self._analyze_heading_hierarchy(headings)

            return {
                "headings": headings,
                "count": len(headings),
                "hierarchy_issues": hierarchy_issues
            }
        except Exception as e:
            self._logger.warning(f"Failed to extract headings: {e}")
            return {"headings": [], "count": 0, "hierarchy_issues": []}

    def _analyze_heading_hierarchy(self, headings: List[Dict]) -> List[Dict]:

        issues = []
        last_level = 0

        for i, heading in enumerate(headings):
            current_level = heading["level"]


            if last_level > 0 and current_level > last_level + 1:
                issues.append({
                    "type": "heading_skip",
                    "description": f"Heading level skipped from h{last_level} to h{current_level}",
                    "index": i,
                    "heading": heading,
                    "severity": "moderate"
                })


            if not heading["text"].strip() and heading["isVisible"]:
                issues.append({
                    "type": "empty_heading",
                    "description": f"Heading h{current_level} has no text content",
                    "index": i,
                    "heading": heading,
                    "severity": "serious"
                })

            last_level = current_level

        return issues

    async def _get_landmark_regions(self, page: Page) -> List[Dict[str, Any]]:

        js_code = """
        () => {
            const roles = ['main', 'nav', 'header', 'footer', 'aside', 'section', 'article', 'form', 'search'];
            return Array.from(document.querySelectorAll(roles.map(r => `[role="${r}"], ${r}`).join(',')))
                .map(el => ({
                    role: el.getAttribute('role') || el.tagName.toLowerCase(),
                    label: el.getAttribute('aria-label'),
                    labelledby: el.getAttribute('aria-labelledby')
                }));
        }
        """

        try:
            landmarks = await page.evaluate(js_code)


            issues = self._analyze_landmarks(landmarks)

            return {
                "landmarks": landmarks,
                "count": len(landmarks),
                "issues": issues
            }
        except Exception as e:
            self._logger.warning(f"Failed to extract landmarks: {e}")
            return {"landmarks": [], "count": 0, "issues": []}

    def _analyze_landmarks(self, landmarks: List[Dict]) -> List[Dict]:

        issues = []
        role_counts = {}


        has_main = any(l["role"] == "main" for l in landmarks)
        if not has_main:
            issues.append({
                "type": "missing_main",
                "description": "No main landmark found",
                "severity": "serious"
            })


        for landmark in landmarks:
            role = landmark["role"]
            if role in role_counts:
                role_counts[role] += 1
            else:
                role_counts[role] = 1

        for role, count in role_counts.items():
            if count > 1 and role not in ["region"]:

                dupes = [l for l in landmarks if l["role"] == role]
                unlabeled = [l for l in dupes if not l["label"] and not l["labelledby"]]

                if unlabeled:
                    issues.append({
                        "type": "duplicate_landmark",
                        "description": f"Multiple {role} landmarks without unique labels",
                        "count": len(unlabeled),
                        "severity": "moderate"
                    })

        return issues

    async def _get_focusable_elements(self, page: Page) -> List[Dict[str, Any]]:

        js_code = """
        () => {
            return Array.from(document.querySelectorAll('a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])'))
                .map(el => ({
                    tag: el.tagName.toLowerCase(),
                    text: el.innerText.trim() || el.value || '',
                    role: el.getAttribute('role')
                }));
        }
        """

        try:
            return await page.evaluate(js_code)
        except Exception as e:
            self._logger.warning(f"Failed to extract focusable elements: {e}")
            return []

    async def _compute_statistics(self, page: Page, structure: Dict) -> Dict[str, Any]:

        try:

            total_elements = await page.evaluate('document.querySelectorAll("*").length')


            image_stats = await page.evaluate("() => { const imgs = Array.from(document.images); return { total: imgs.length, with_alt: imgs.filter(i => i.alt).length, without_alt: imgs.filter(i => !i.alt).length }; }")


            form_stats = await page.evaluate("() => { const forms = Array.from(document.forms); return { total: forms.length, with_label: Array.from(document.querySelectorAll('input, select, textarea')).filter(i => i.labels && i.labels.length > 0).length }; }")

            return {
                "total_elements": total_elements,
                "images": image_stats,
                "forms": form_stats,
                "headings": len(structure.get("headings", {}).get("headings", [])),
                "landmarks": len(structure.get("landmarks", {}).get("landmarks", [])),
                "focusable_elements": len(structure.get("focusable_elements", []))
            }
        except Exception as e:
            self._logger.warning(f"Failed to compute statistics: {e}")
            return {}

    def _get_timestamp(self) -> str:

        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()