


from .base import BaseAccessibilityEngine
from .registry import EngineRegistry
from .wcag_engine import WCAGEngine
from .contrast_engine import ContrastEngine
from .structural_engine import StructuralEngine
try:
    from .ai_engine import AIEngine
except ImportError:
    AIEngine = None

__all__ = [
    'BaseAccessibilityEngine',
    'EngineRegistry',
    'WCAGEngine',
    'ContrastEngine',
    'StructuralEngine',
    'AIEngine'
]


__version__ = '1.0.0'