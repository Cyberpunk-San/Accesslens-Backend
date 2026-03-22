
from typing import List, Dict, Any
from ..models.schemas import UnifiedIssue, IssueSeverity, ConfidenceLevel

class ConfidenceCalculator:


    @staticmethod
    def calculate_confidence(
        source: str,
        factors: Dict[str, float],
        base_confidence: float = 100.0
    ) -> float:

        weights = {
            "wcag_deterministic": {
                "detection_reliability": 0.5,
                "context_clarity": 0.2,
                "pattern_match": 0.1,
                "evidence_quality": 0.2
            },
            "structural": {
                "detection_reliability": 0.3,
                "context_clarity": 0.3,
                "pattern_match": 0.2,
                "evidence_quality": 0.2
            },
            "contrast": {
                "detection_reliability": 0.4,
                "context_clarity": 0.3,
                "pattern_match": 0.1,
                "evidence_quality": 0.2
            },
            "ai_contextual": {
                "detection_reliability": 0.2,
                "context_clarity": 0.3,
                "pattern_match": 0.2,
                "evidence_quality": 0.3
            }
        }

        source_weights = weights.get(source, weights["wcag_deterministic"])

        weighted_score = sum(
            factors.get(factor, 1.0) * weight
            for factor, weight in source_weights.items()
        )


        confidence = min(100, max(0, weighted_score * 100))

        return round(confidence, 2)

    @staticmethod
    def confidence_to_level(score: float) -> ConfidenceLevel:

        if score >= 95:
            return ConfidenceLevel.HIGH
        elif score >= 70:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

class SeverityMapper:


    SEVERITY_MATRIX = {
        "missing_alt": {
            "impact": IssueSeverity.CRITICAL,
            "wcag": "1.1.1",
            "description": "Images missing alternative text"
        },
        "low_contrast": {
            "impact": IssueSeverity.SERIOUS,
            "wcag": "1.4.3",
            "description": "Text contrast below 4.5:1"
        },
        "empty_button": {
            "impact": IssueSeverity.CRITICAL,
            "wcag": "4.1.2",
            "description": "Button has no accessible name"
        },
        "heading_skip": {
            "impact": IssueSeverity.MODERATE,
            "wcag": "1.3.1",
            "description": "Heading level skipped"
        },
        "missing_landmark": {
            "impact": IssueSeverity.SERIOUS,
            "wcag": "1.3.1",
            "description": "Missing landmark regions"
        }
    }

    @classmethod
    def get_severity(cls, issue_type: str, context: Dict[str, Any] = None) -> IssueSeverity:

        base = cls.SEVERITY_MATRIX.get(
            issue_type,
            {"impact": IssueSeverity.MINOR}
        )

        if context and context.get("user_impact", "").lower() == "blocking":
            return IssueSeverity.CRITICAL

        return base["impact"]