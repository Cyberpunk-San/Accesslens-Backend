from typing import List, Dict, Any

class HeadingHierarchyAnalyzer:


    def analyze(self, headings: List[Dict[str, Any]]) -> Dict[str, Any]:

        issues = []
        outline = []

        if not headings:
            issues.append({
                "type": "no_headings",
                "description": "Page has no headings",
                "severity": "serious",
                "wcag": "1.3.1"
            })
            return {"issues": issues, "outline": outline}

        h1_count = 0
        last_level = 0

        for index, heading in enumerate(headings):
            level = heading.get("level", 0)
            text = heading.get("text", "")

            outline.append({
                "level": level,
                "text": text,
                "selector": heading.get("selector")
            })


            if level == 1:
                h1_count += 1
                if h1_count > 1:
                    issues.append({
                        "type": "multiple_h1",
                        "description": "Multiple H1 headings found",
                        "severity": "moderate",
                        "location": {"selector": heading.get("selector"), "index": index},
                        "wcag": "1.3.1"
                    })


            if not text.strip():
                issues.append({
                    "type": "empty_heading",
                    "description": "Heading has no text content",
                    "severity": "serious",
                    "location": {"selector": heading.get("selector"), "index": index},
                    "wcag": "1.3.1"
                })


            if not heading.get("isVisible", True):
                issues.append({
                    "type": "hidden_heading",
                    "description": "Heading is hidden from users",
                    "severity": "minor",
                    "location": {"selector": heading.get("selector"), "index": index},
                    "wcag": "1.3.1"
                })


            if last_level > 0 and (level - last_level) > 1:
                issues.append({
                    "type": "heading_skip",
                    "description": f"Heading levels skipped: H{last_level} to H{level}. Screen reader users rely on hierarchical order to understand content structure.",
                    "severity": "moderate",
                    "location": {"selector": heading.get("selector"), "index": index},
                    "wcag": "1.3.1",
                    "context": f"Previous: H{last_level}, Current: H{level}"
                })

            if level > 6:
                 issues.append({
                    "type": "deep_nesting",
                    "description": f"Heading level H{level} is nesting very deeply. Consider restructuring content for better readability.",
                    "severity": "minor",
                    "location": {"selector": heading.get("selector"), "index": index},
                    "wcag": "1.3.1"
                })

            last_level = level

        if h1_count == 0:
            issues.append({
                "type": "missing_h1",
                "description": "Missing H1 heading",
                "severity": "serious",
                "wcag": "1.3.1"
            })

        return {
            "issues": issues,
            "outline": outline,
            "structure": outline
        }