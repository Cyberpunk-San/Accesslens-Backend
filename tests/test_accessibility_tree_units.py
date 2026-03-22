import pytest
pytestmark = pytest.mark.unit

from app.core.accessibility_tree import AccessibilityTreeExtractor

@pytest.fixture
def extractor():
    return AccessibilityTreeExtractor()

def test_analyze_heading_hierarchy_skips(extractor):
    headings = [
        {"level": 1, "text": "H1", "isVisible": True},
        {"level": 3, "text": "H3", "isVisible": True}, # Skip H2
        {"level": 4, "text": "H4", "isVisible": True},
        {"level": 6, "text": "H6", "isVisible": True}, # Skip H5
    ]
    issues = extractor._analyze_heading_hierarchy(headings)
    assert len(issues) == 2
    assert issues[0]["type"] == "heading_skip"
    assert "h1 to h3" in issues[0]["description"].lower()
    assert "h4 to h6" in issues[1]["description"].lower()

def test_analyze_heading_hierarchy_empty(extractor):
    headings = [
        {"level": 1, "text": "", "isVisible": True},
        {"level": 2, "text": "  ", "isVisible": True},
    ]
    issues = extractor._analyze_heading_hierarchy(headings)
    assert len(issues) == 2
    assert issues[0]["type"] == "empty_heading"

def test_analyze_landmarks_missing_main(extractor):
    landmarks = [
        {"role": "header", "label": "Header"},
        {"role": "footer", "label": "Footer"},
    ]
    issues = extractor._analyze_landmarks(landmarks)
    assert any(i["type"] == "missing_main" for i in issues)

def test_analyze_landmarks_duplicates_unlabeled(extractor):
    landmarks = [
        {"role": "main", "label": "Main Content"},
        {"role": "nav", "label": None, "labelledby": None},
        {"role": "nav", "label": "", "labelledby": ""},
    ]
    issues = extractor._analyze_landmarks(landmarks)
    assert any(i["type"] == "duplicate_landmark" for i in issues)

def test_normalize_accessibility_nodes(extractor):
    raw_nodes = [
        {
            "nodeId": "1",
            "role": {"value": "button"},
            "name": {"value": "Submit"},
            "properties": [
                {"name": "pressed", "value": {"value": "true"}}
            ],
            "childIds": ["2"]
        }
    ]
    normalized = extractor._normalize_accessibility_nodes(raw_nodes)
    assert len(normalized) == 1
    assert normalized[0]["role"] == "button"
    assert normalized[0]["properties"]["pressed"] == "true"

def test_count_nodes(extractor):
    tree = {
        "children": [
            {"children": []},
            {"children": [{"children": []}]}
        ]
    }
    assert extractor._count_nodes(tree) == 4
