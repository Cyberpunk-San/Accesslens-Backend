# tests/test_color_utils_more.py

import pytest
pytestmark = pytest.mark.unit

from app.core.color_utils import ColorParser, RGBColor, ContrastCalculator

class TestColorUtilsCoverage:
    """Test color utilities edge cases"""
    
    def test_color_parser_named_colors(self):
        """Test parsing named colors"""
        colors = {
            "red": (255, 0, 0),
            "green": (0, 128, 0),
            "blue": (0, 0, 255),
            "black": (0, 0, 0),
            "white": (255, 255, 255),
        }
        for name, rgb in colors.items():
            result = ColorParser.parse(name)
            assert result is not None
            assert (result.r, result.g, result.b) == rgb
    
    def test_color_parser_invalid(self):
        """Test invalid color parsing"""
        assert ColorParser.parse("") is None
        assert ColorParser.parse("invalid") is None
        assert ColorParser.parse("transparent") is None
        assert ColorParser.parse(None) is None
    
    def test_color_parser_hex_edge_cases(self):
        """Test hex color edge cases"""
        # 3-digit hex
        assert ColorParser.parse("#F00") == RGBColor(255, 0, 0)
        # 6-digit hex
        assert ColorParser.parse("#00FF00") == RGBColor(0, 255, 0)
        # Invalid hex
        assert ColorParser.parse("#GGGGGG") is None
    
    def test_color_parser_rgb_edge_cases(self):
        """Test RGB color edge cases"""
        assert ColorParser.parse("rgb(255,255,255)") == RGBColor(255, 255, 255)
        assert ColorParser.parse("rgba(255,0,0,0.5)") == RGBColor(255, 0, 0, 0.5)
        assert ColorParser.parse("rgb(300,0,0)") is None  # Out of range
    
    def test_contrast_calculator_edge_cases(self):
        """Test contrast calculator edge cases"""
        black = RGBColor(0, 0, 0)
        white = RGBColor(255, 255, 255)
        
        # Same color
        assert ContrastCalculator.calculate_ratio(black, black) == 1.0
        
        # Max contrast
        assert ContrastCalculator.calculate_ratio(black, white) == 21.0
        
        # Grade calculation
        grade = ContrastCalculator.get_grade(4.5)
        assert grade["aa_normal"] is True
        assert grade["grade"] == "AA"
