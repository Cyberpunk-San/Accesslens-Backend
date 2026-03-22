import pytest
pytestmark = pytest.mark.unit

from app.core.color_utils import RGBColor, ColorParser, ContrastCalculator

def test_color_parser_edge_cases():
    """Verify ColorParser handles malformed input gracefully."""
    # Hex
    assert ColorParser.parse("#FFFFFF") == RGBColor(255, 255, 255)
    assert ColorParser.parse("FFF") == RGBColor(255, 255, 255) # Assuming parsing FFF as FFFFFF
    assert ColorParser.parse("garbage") is None
    assert ColorParser.parse(None) is None
    
    # CSS Formats
    assert ColorParser.parse("rgb(255, 255, 255)") == RGBColor(255, 255, 255)
    assert ColorParser.parse("rgba(100, 100, 100, 0.5)") == RGBColor(100, 100, 100, 0.5)
    assert ColorParser.parse("var(--primary)") is None
    assert ColorParser.parse("") is None

def test_luminance_and_contrast_boundaries():
    """Verify luminance calculations on extreme RGB values."""
    white = RGBColor(255, 255, 255)
    black = RGBColor(0, 0, 0)
    
    assert white.to_luminance() > 0.99
    assert black.to_luminance() < 0.01

    assert ContrastCalculator.calculate_ratio(white, black) == pytest.approx(21.0)
    assert ContrastCalculator.calculate_ratio(black, black) == pytest.approx(1.0)
