import pytest
from app.core.scoring import ConfidenceCalculator
from app.models.schemas import ConfidenceLevel

def test_calculate_confidence_base():
    weights = {
        "detection_reliability": 1.0,
        "context_clarity": 1.0,
        "pattern_match": 1.0,
        "evidence_quality": 1.0
    }
    score = ConfidenceCalculator.calculate_confidence("test_engine", weights)
    assert score == 100

def test_calculate_confidence_low():
    weights = {
        "detection_reliability": 0.5,
        "context_clarity": 0.5,
        "pattern_match": 0.5,
        "evidence_quality": 0.5
    }
    score = ConfidenceCalculator.calculate_confidence("test_engine", weights)
    assert score == 50

def test_confidence_to_level():
    assert ConfidenceCalculator.confidence_to_level(95) == ConfidenceLevel.HIGH
    assert ConfidenceCalculator.confidence_to_level(75) == ConfidenceLevel.MEDIUM
    assert ConfidenceCalculator.confidence_to_level(40) == ConfidenceLevel.LOW
