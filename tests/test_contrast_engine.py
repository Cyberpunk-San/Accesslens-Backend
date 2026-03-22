


import pytest
from playwright.async_api import async_playwright
from app.engines.contrast_engine import ContrastEngine
from app.core.color_utils import ColorParser, ContrastCalculator, RGBColor

@pytest.mark.asyncio
async def test_color_parser():



    rgb = ColorParser.parse("#FF0000")
    assert rgb is not None
    assert rgb.r == 255
    assert rgb.g == 0
    assert rgb.b == 0


    rgb = ColorParser.parse("#f00")
    assert rgb is not None
    assert rgb.r == 255
    assert rgb.g == 0
    assert rgb.b == 0


    rgb = ColorParser.parse("rgb(0, 255, 0)")
    assert rgb is not None
    assert rgb.r == 0
    assert rgb.g == 255
    assert rgb.b == 0


    rgb = ColorParser.parse("rgba(0, 0, 255, 0.5)")
    assert rgb is not None
    assert rgb.r == 0
    assert rgb.g == 0
    assert rgb.b == 255


    rgb = ColorParser.parse("red")
    assert rgb is not None
    assert rgb.r == 255
    assert rgb.g == 0
    assert rgb.b == 0

    rgb = ColorParser.parse("white")
    assert rgb is not None
    assert rgb.r == 255
    assert rgb.g == 255
    assert rgb.b == 255


    assert ColorParser.parse("invalid") is None
    assert ColorParser.parse("") is None

@pytest.mark.asyncio
async def test_contrast_calculation():



    black = RGBColor(0, 0, 0)
    white = RGBColor(255, 255, 255)
    ratio = ContrastCalculator.calculate_ratio(black, white)
    assert ratio == 21.0


    red = RGBColor(255, 0, 0)
    same_red = RGBColor(255, 0, 0)
    ratio = ContrastCalculator.calculate_ratio(red, same_red)
    assert ratio == 1.0


    test_cases = [
        (RGBColor(0, 0, 0), RGBColor(255, 255, 255), 21.0),
        (RGBColor(255, 255, 255), RGBColor(0, 0, 0), 21.0),
        (RGBColor(128, 128, 128), RGBColor(255, 255, 255), 3.94),
        (RGBColor(0, 0, 255), RGBColor(255, 255, 255), 8.59),
    ]

    for fg, bg, expected in test_cases:
        ratio = ContrastCalculator.calculate_ratio(fg, bg)
        assert abs(ratio - expected) < 0.1

@pytest.mark.asyncio
async def test_contrast_thresholds():



    assert ContrastCalculator.meets_threshold(4.5, "AA", False) is True
    assert ContrastCalculator.meets_threshold(4.4, "AA", False) is False


    assert ContrastCalculator.meets_threshold(3.0, "AA", True) is True
    assert ContrastCalculator.meets_threshold(2.9, "AA", True) is False


    assert ContrastCalculator.meets_threshold(7.0, "AAA", False) is True
    assert ContrastCalculator.meets_threshold(6.9, "AAA", False) is False


    assert ContrastCalculator.meets_threshold(4.5, "AAA", True) is True
    assert ContrastCalculator.meets_threshold(4.4, "AAA", True) is False

@pytest.mark.asyncio
async def test_contrast_grades():



    grades = ContrastCalculator.get_grade(5.0)
    assert grades["aa_normal"] is True
    assert grades["aaa_normal"] is False
    assert grades["grade"] == "AA"

    grades = ContrastCalculator.get_grade(8.0)
    assert grades["aa_normal"] is True
    assert grades["aaa_normal"] is True
    assert grades["grade"] == "AAA"

    grades = ContrastCalculator.get_grade(2.0)
    assert grades["aa_normal"] is False
    assert grades["grade"] == "FAIL"


    grades = ContrastCalculator.get_grade(4.0, is_large_text=True)
    assert grades["aa_large"] is True
    assert grades["aaa_large"] is False
    assert grades["grade"] == "AA"

@pytest.mark.asyncio
async def test_contrast_engine_analysis():


    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()


        html = """
        <html>
        <body>
            <div style="background-color: white; color: silver;">Low Contrast Text</div>
            <div style="background-color: black; color: white;">High Contrast Text</div>
        </body>
        </html>
        """

        await page.set_content(html)


        engine = ContrastEngine()


        issues = await engine.analyze(
            {"page": page},
            {}
        )


        assert len(issues) > 0


        issue_types = [i.issue_type for i in issues]
        assert "low_contrast_text" in issue_types


        for issue in issues:
            assert issue.source.value == "contrast"
            assert issue.confidence_score > 0
            assert len(issue.wcag_criteria) > 0

        await browser.close()