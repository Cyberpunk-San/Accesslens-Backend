from pydantic import BaseModel, Field, field_validator, ValidationInfo
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime, timezone
import uuid

class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    SERIOUS = "serious"
    MODERATE = "moderate"
    MINOR = "minor"

class IssueSource(str, Enum):
    WCAG_DETERMINISTIC = "wcag_deterministic"
    STRUCTURAL = "structural"
    CONTRAST = "contrast"
    AI_CONTEXTUAL = "ai_contextual"
    HEURISTIC = "heuristic"

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    PROBABILISTIC = "probabilistic"

class WCAGLevel(str, Enum):
    A = "A"
    AA = "AA"
    AAA = "AAA"

class TaskPriority(str, Enum):
    P0 = "P0" # Critical impact, fix immediately
    P1 = "P1" # High impact, high priority
    P2 = "P2" # Moderate impact
    P3 = "P3" # Low impact / Best practice

class WCAGCriteria(BaseModel):

    id: str
    level: WCAGLevel
    title: str
    description: Optional[str] = None
    url: Optional[str] = None

class ElementLocation(BaseModel):

    selector: str
    xpath: Optional[str] = None
    html: Optional[str] = None
    node_index: Optional[int] = None
    iframe_index: Optional[int] = None

    shadow_root_path: Optional[List[str]] = None
    bounding_box: Optional[Dict[str, float]] = None

class RemediationSuggestion(BaseModel):
    """
    Suggested fix for an accessibility issue.
    """
    description: str
    code_before: Optional[str] = None
    code_after: Optional[str] = None
    estimated_effort: Optional[str] = None # low, medium, high
    estimated_fix_hours: Optional[float] = None # Estimated developer hours
    verification_steps: List[str] = [] # Concrete steps to verify the fix

class EvidenceData(BaseModel):

    screenshot: Optional[str] = None
    stack_trace: Optional[Union[Dict[str, Any], str]] = None
    computed_values: Optional[Dict[str, Any]] = None
    dom_snapshot: Optional[Dict[str, Any]] = None
    ai_reasoning: Optional[str] = None
    code_snippet: Optional[str] = None

class UnifiedIssue(BaseModel):

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)


    title: str
    description: str
    issue_type: str


    severity: IssueSeverity
    confidence: ConfidenceLevel
    confidence_score: float = Field(ge=0, le=100)
    source: IssueSource
    priority: TaskPriority = Field(default=TaskPriority.P2)


    wcag_criteria: List[WCAGCriteria] = []


    location: Optional[ElementLocation] = None


    actual_value: Optional[str] = None
    expected_value: Optional[str] = None


    remediation: Optional[RemediationSuggestion] = None


    evidence: Optional[EvidenceData] = None


    engine_name: str
    engine_version: Optional[str] = None
    tags: List[str] = []

    @field_validator('confidence_score')
    @classmethod
    def validate_confidence(cls, v: float, info: ValidationInfo) -> float:
        if 'confidence' in info.data:
            confidence = info.data['confidence']
            if confidence == ConfidenceLevel.HIGH and v < 95:
                raise ValueError('HIGH confidence requires score >= 95')
            elif confidence == ConfidenceLevel.MEDIUM and (v < 70 or v >= 95):
                raise ValueError('MEDIUM confidence requires 70 <= score < 95')
            elif confidence == ConfidenceLevel.LOW and v >= 70:
                raise ValueError('LOW confidence requires score < 70')
        return v

class AuditRequest(BaseModel):

    url: str
    engines: List[str] = ["wcag", "structural", "contrast", "heuristic", "navigation", "form"]
    enable_ai: bool = False
    depth: str = "standard"
    viewport: Dict[str, int] = {"width": 1280, "height": 720}
    wait_for_network_idle: bool = True

class AuditSummary(BaseModel):

    total_issues: int
    by_severity: Dict[IssueSeverity, int]
    by_source: Dict[IssueSource, int]
    by_wcag_level: Dict[str, int]
    score: float
    confidence_avg: float
    error: Optional[str] = None
    coverage_comparator: Dict[str, Any] = Field(default_factory=dict)
    contrast_patterns: List[Dict[str, Any]] = Field(default_factory=list) # List of grouped contrast issues

class AuditReport(BaseModel):

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request: AuditRequest
    timestamp: datetime = Field(default_factory=datetime.now)
    summary: AuditSummary
    issues: List[UnifiedIssue]
    accessibility_tree: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {}