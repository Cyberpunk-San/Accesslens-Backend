


import pytest
from playwright.async_api import async_playwright
from app.engines.structural_engine import StructuralEngine
from app.core.heading_analyzer import HeadingHierarchyAnalyzer
from app.core.landmark_validator import LandmarkValidator

@pytest.mark.asyncio
async def test_heading_analyzer():


    headings = [
        {"level": 1, "text": "Main Title", "selector": "h1", "isVisible": True},
        {"level": 2, "text": "Section 1", "selector": "h2", "isVisible": True},
        {"level": 4, "text": "Skip to H4", "selector": "h4", "isVisible": True},
        {"level": 2, "text": "", "selector": "h2", "isVisible": True},
        {"level": 3, "text": "Hidden", "selector": "h3", "isVisible": False},
    ]

    analyzer = HeadingHierarchyAnalyzer()
    result = analyzer.analyze(headings)

    assert "issues" in result
    assert "structure" in result
    assert "outline" in result


    issue_types = [i["type"] for i in result["issues"]]
    assert "heading_skip" in issue_types
    assert "empty_heading" in issue_types


    assert len(result["outline"]) > 0

@pytest.mark.asyncio
async def test_landmark_validator():


    landmarks = [
        {"role": "banner", "selector": "header", "label": None, "tag": "header"},
        {"role": "navigation", "selector": "nav", "label": "Main", "tag": "nav"},
        {"role": "main", "selector": "main", "label": None, "tag": "main"},
        {"role": "navigation", "selector": "nav", "label": None, "tag": "nav"},
        {"role": "region", "selector": "section", "label": None, "tag": "section", "hasHeading": False},
    ]

    validator = LandmarkValidator()
    result = validator.validate(landmarks)

    assert "issues" in result
    assert "landmarks" in result
    assert "structure" in result


    issue_types = [i["type"] for i in result["issues"]]
    assert "navigation_unlabeled" in issue_types
    assert "region_no_heading" in issue_types

@pytest.mark.asyncio
async def test_structural_engine_full():


    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()


        html = """
        <html>
        <body>
            <h1>Structural Test Page</h1>
            <h1>Another H1</h1> <!-- Semantic issue -->
            <h3>Skipped H2</h3> <!-- Semantic issue -->
            <nav>
                <a href="/">Home</a>
            </nav>
            <nav>
                <a href="/products">Products</a>
            </nav> <!-- Unlabeled duplicate nav -->
        </body>
        </html>
        """

        await page.set_content(html)


        engine = StructuralEngine()


        issues = await engine.analyze(
            {"page": page},
            {}
        )


        assert len(issues) > 0


        issue_types = [i.issue_type for i in issues]
        assert "multiple_h1" in issue_types or "heading_skip" in issue_types


        for issue in issues:
            assert issue.source.value == "structural"
            assert issue.confidence_score > 0
            assert issue.engine_name == "structural_engine"

        await browser.close()