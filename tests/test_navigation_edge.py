import pytest
from unittest.mock import AsyncMock
from app.engines.navigation_engine import NavigationEngine
from app.models.schemas import AuditRequest

pytestmark = pytest.mark.unit

@pytest.fixture
def nav_engine():
    return NavigationEngine()

@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.evaluate.return_value = []
    page.keyboard = AsyncMock()
    return page

@pytest.mark.asyncio
async def test_navigation_empty_page(nav_engine, mock_page):
    request = AuditRequest(url="https://test.com")
    issues = await nav_engine.analyze({"page": mock_page}, request)
    assert len(issues) == 0

@pytest.mark.asyncio
async def test_navigation_landmarks_duplicate(nav_engine, mock_page):
    tree = {
        "role": "main",
        "name": "Main Content",
        "children": [
            {"role": "navigation", "name": "Primary Nav"},
            {"role": "navigation", "name": "Primary Nav"}
        ]
    }
    request = AuditRequest(url="https://test.com")
    issues = await nav_engine.analyze({"page": mock_page, "accessibility_tree": tree}, request)
    assert any(i.issue_type == "DUPLICATE_LANDMARK_LABEL" for i in issues)

@pytest.mark.asyncio
async def test_navigation_landmarks_multiple_main(nav_engine, mock_page):
    tree = {
        "role": "root",
        "children": [
            {"role": "main", "name": "Main 1"},
            {"role": "main", "name": "Main 2"}
        ]
    }
    request = AuditRequest(url="https://test.com")
    issues = await nav_engine.analyze({"page": mock_page, "accessibility_tree": tree}, request)
    assert any(i.issue_type == "MULTIPLE_MAIN_LANDMARKS" for i in issues)

@pytest.mark.asyncio
async def test_navigation_focus_trap_critical(nav_engine, mock_page):
    focusable_elements = [
        {"id": "trap1", "tagName": "div", "html": "<div id='trap1'></div>", "text": ""},
        {"id": "dummy", "tagName": "div", "html": "<div id='dummy'></div>", "text": ""}
    ]
    call_count = 0
    def mock_evaluate(script, *args):
        nonlocal call_count
        call_count += 1
        if "const noIndicator =" in script:
            return []
        if "document.querySelectorAll" in script:
            return focusable_elements
        if "document.activeElement" in script:
            return {"tagName": "DIV", "id": "trap1", "html": "<div id='trap1'></div>", "text": "trap"}
        return []
    mock_page.evaluate.side_effect = mock_evaluate
    request = AuditRequest(url="https://test.com")
    issues = await nav_engine.analyze({"page": mock_page}, request)
    assert any(i.issue_type == "FOCUS_TRAP" for i in issues)

@pytest.mark.asyncio
async def test_navigation_reverse_focus_trap(nav_engine, mock_page):
    focusable_elements = [
        {"id": "btn1", "tagName": "BUTTON", "html": "<button id='btn1'>1</button>", "text": "1"},
        {"id": "btn2", "tagName": "BUTTON", "html": "<button id='btn2'>2</button>", "text": "2"}
    ]
    call_count = 0
    def mock_evaluate(script, *args):
        nonlocal call_count
        call_count += 1
        if "const noIndicator =" in script:
            return []
        if "document.querySelectorAll" in script:
            return focusable_elements
        if "document.activeElement" in script:
            if call_count < 4: 
                return {"tagName": "BUTTON", "id": f"btn{call_count}", "html": f"<button id='btn{call_count}'></button>", "text": str(call_count)}
            return {"tagName": "BUTTON", "id": "btn_trap", "html": "<button id='btn_trap'></button>", "text": "trap"}
        return []
    mock_page.evaluate.side_effect = mock_evaluate
    request = AuditRequest(url="https://test.com")
    issues = await nav_engine.analyze({"page": mock_page}, request)
    assert any(i.issue_type == "REVERSE_FOCUS_TRAP" for i in issues)

@pytest.mark.asyncio
async def test_navigation_focus_indicator(nav_engine, mock_page):
    def mock_evaluate(script, *args):
        if "const noIndicator =" in script:
            return [{"tag": "button", "id": "btn_bad", "html": "<button id='btn_bad'></button>"}]
        if "document.querySelectorAll" in script:
            return []
        return []
    mock_page.evaluate.side_effect = mock_evaluate
    request = AuditRequest(url="https://test.com")
    issues = await nav_engine.analyze({"page": mock_page}, request)
    assert any(i.issue_type == "MISSING_FOCUS_INDICATOR" for i in issues)
    
@pytest.mark.asyncio
async def test_navigation_focus_flow_exception(nav_engine, mock_page):
    mock_page.evaluate.side_effect = Exception("Browser Crash")
    request = AuditRequest(url="https://test.com")
    issues = await nav_engine.analyze({"page": mock_page}, request)
    assert len(issues) == 0
