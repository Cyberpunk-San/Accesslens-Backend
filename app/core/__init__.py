"""
Core Configuration and Utilities Module

This package contains the essential components for the AccessLens backend:
- Configuration schemas and parsers (`config.py`)
- Core application lifecycle and state classes.
- Playwright-based browser pool managers (`browser_manager.py`).
- Navigation and metric extraction controllers (`page_controller.py`).
- Universal logic handlers like `audit_orchestrator.py` and `color_utils.py`.
- Persistence adapters for the SQLite database (`report_storage.py`).

These classes are typically stateless singletons or heavily managed to handle
high-concurrency request workloads securely.
"""
from .config import settings
from .browser_manager import browser_manager
from .report_storage import report_storage
from .logging_config import setup_logging
from .page_controller import PageController
from .accessibility_tree import AccessibilityTreeExtractor
from .color_utils import ColorParser, ContrastCalculator, RGBColor
from .heading_analyzer import HeadingHierarchyAnalyzer
from .landmark_validator import LandmarkValidator
from .scoring import ConfidenceCalculator, SeverityMapper
from .audit_orchestrator import AuditOrchestrator

__all__ = [
    'settings',
    'browser_manager',
    'report_storage',
    'setup_logging',
    'PageController',
    'AccessibilityTreeExtractor',
    'ColorParser',
    'ContrastCalculator',
    'RGBColor',
    'HeadingHierarchyAnalyzer',
    'LandmarkValidator',
    'ConfidenceCalculator',
    'SeverityMapper',
    'AuditOrchestrator'
]

__version__ = '1.0.0'