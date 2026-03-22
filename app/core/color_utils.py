
import re
import math
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class RGBColor:
    r: int
    g: int
    b: int
    a: float = 1.0

    def to_hex(self) -> str:

        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    def to_rgb_string(self) -> str:
        if self.a < 1.0:
            return f"rgba({self.r}, {self.g}, {self.b}, {self.a})"
        return f"rgb({self.r}, {self.g}, {self.b})"

    def blend(self, background: 'RGBColor') -> 'RGBColor':
        """Blends this color with a background color using alpha channel."""
        if self.a >= 1.0:
            return self
        alpha = self.a
        return RGBColor(
            r=int(self.r * alpha + background.r * (1 - alpha)),
            g=int(self.g * alpha + background.g * (1 - alpha)),
            b=int(self.b * alpha + background.b * (1 - alpha)),
            a=1.0
        )

    def to_luminance(self) -> float:

        rs = self.r / 255
        gs = self.g / 255
        bs = self.b / 255


        r = rs / 12.92 if rs <= 0.03928 else ((rs + 0.055) / 1.055) ** 2.4
        g = gs / 12.92 if gs <= 0.03928 else ((gs + 0.055) / 1.055) ** 2.4
        b = bs / 12.92 if bs <= 0.03928 else ((bs + 0.055) / 1.055) ** 2.4


        return 0.2126 * r + 0.7152 * g + 0.0722 * b

class ColorParser:

    @staticmethod
    def parse(color_str: str) -> Optional[RGBColor]:

        if not color_str or color_str == "transparent":
            return None


        if color_str.startswith('rgb'):
            return ColorParser._parse_rgb(color_str)


        elif color_str.startswith('#'):
            return ColorParser._parse_hex(color_str)


        elif color_str in ColorParser.NAMED_COLORS:
            hex_color = ColorParser.NAMED_COLORS[color_str]
            return ColorParser._parse_hex(hex_color)


        elif color_str.startswith('hsl'):
            return ColorParser._parse_hsl(color_str)

        if len(color_str) in [3, 6] and all(c in '0123456789abcdefABCDEF' for c in color_str):
            return ColorParser._parse_hex(color_str)

        return None

    @staticmethod
    def _parse_rgb(rgb_str: str) -> Optional[RGBColor]:
        # Handle both rgb and rgba
        pattern = r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)'
        match = re.match(pattern, rgb_str.strip())

        if match:
            r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
            a = float(match.group(4)) if match.group(4) else 1.0
            if all(0 <= c <= 255 for c in (r, g, b)) and 0 <= a <= 1:
                return RGBColor(r=r, g=g, b=b, a=a)
        return None

    @staticmethod
    def _parse_hex(hex_str: str) -> Optional[RGBColor]:

        hex_str = hex_str.lstrip('#')


        if len(hex_str) == 3:
            hex_str = ''.join([c*2 for c in hex_str])

        if len(hex_str) == 6:
            try:
                return RGBColor(
                    r=int(hex_str[0:2], 16),
                    g=int(hex_str[2:4], 16),
                    b=int(hex_str[4:6], 16)
                )
            except ValueError:
                return None

        return None

    @staticmethod
    def _parse_hsl(hsl_str: str) -> Optional[RGBColor]:

        pattern = r'hsla?\((\d+),\s*(\d+)%?,\s*(\d+)%?(?:,\s*[\d.]+)?\)'
        match = re.match(pattern, hsl_str.strip())

        if not match:
            return None

        h = int(match.group(1)) / 360
        s = int(match.group(2)) / 100
        l = int(match.group(3)) / 100
        a = float(match.group(4)) if match.group(4) else 1.0

        if s == 0:
            r = g = b = l
        else:
            def hue_to_rgb(p, q, t):
                if t < 0: t += 1
                if t > 1: t -= 1
                if t < 1/6: return p + (q - p) * 6 * t
                if t < 1/2: return q
                if t < 2/3: return p + (q - p) * (2/3 - t) * 6
                return p

            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q

            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)

        return RGBColor(
            r=int(round(r * 255)),
            g=int(round(g * 255)),
            b=int(round(b * 255)),
            a=a
        )


    NAMED_COLORS = {
        'black': '#000000',
        'silver': '#c0c0c0',
        'gray': '#808080',
        'white': '#ffffff',
        'maroon': '#800000',
        'red': '#ff0000',
        'purple': '#800080',
        'fuchsia': '#ff00ff',
        'green': '#008000',
        'lime': '#00ff00',
        'olive': '#808000',
        'yellow': '#ffff00',
        'navy': '#000080',
        'blue': '#0000ff',
        'teal': '#008080',
        'aqua': '#00ffff',
        'orange': '#ffa500'
    }

class ContrastCalculator:
    @staticmethod
    def calculate_ratio(color1: RGBColor, color2: RGBColor) -> float:

        l1 = color1.to_luminance()
        l2 = color2.to_luminance()

        lighter = max(l1, l2)
        darker = min(l1, l2)

        ratio = (lighter + 0.05) / (darker + 0.05)
        return round(ratio, 2)

    @staticmethod
    def meets_threshold(ratio: float, level: str = "AA", is_large_text: bool = False) -> bool:

        thresholds = {
            "AA": {
                "normal": 4.5,
                "large": 3.0
            },
            "AAA": {
                "normal": 7.0,
                "large": 4.5
            }
        }

        required = thresholds[level]["large" if is_large_text else "normal"]
        return ratio >= required

    @staticmethod
    def get_grade(ratio: float, is_large_text: bool = False) -> Dict[str, Any]:

        result = {
            "ratio": ratio,
            "aa_normal": ratio >= 4.5,
            "aa_large": ratio >= 3.0,
            "aaa_normal": ratio >= 7.0,
            "aaa_large": ratio >= 4.5,
            "grade": "FAIL"
        }

        if is_large_text:
            if ratio >= 4.5:
                result["grade"] = "AAA"
            elif ratio >= 3.0:
                result["grade"] = "AA"
            else:
                result["grade"] = "FAIL"
        else:
            if ratio >= 7.0:
                result["grade"] = "AAA"
            elif ratio >= 4.5:
                result["grade"] = "AA"
            else:
                result["grade"] = "FAIL"

        return result