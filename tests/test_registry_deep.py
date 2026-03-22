import pytest
pytestmark = pytest.mark.unit

from unittest.mock import MagicMock
from app.engines.registry import EngineRegistry
from app.engines.base import BaseAccessibilityEngine

class MockEngine(BaseAccessibilityEngine):
    def __init__(self, name="mock", capabilities=None):
        self._name = name
        self._capabilities = capabilities or ["test"]
        self.initialized = False
        self.shutdown_called = False
    
    @property
    def name(self): return self._name
    @property
    def version(self): return "1.0"
    @property
    def capabilities(self): return self._capabilities
    
    def can_handle(self, capability): return capability in self._capabilities
    async def analyze(self, page, request): return []
    def validate_config(self): return True
    def initialize(self): self.initialized = True
    def shutdown(self): self.shutdown_called = True

@pytest.fixture
def registry():
    return EngineRegistry()

def test_registry_register_unregister(registry):
    engine = MockEngine("e1")
    registry.register(engine)
    assert "e1" in registry
    assert registry.get("e1") == engine
    assert len(registry) == 1
    
    # Overwrite warning check
    engine2 = MockEngine("e1")
    registry.register(engine2)
    assert registry.get("e1") == engine2
    
    registry.unregister("e1")
    assert "e1" not in registry
    assert len(registry) == 0

def test_registry_get_by_capability(registry):
    e1 = MockEngine("e1", ["vision", "contrast"])
    e2 = MockEngine("e2", ["contrast", "structural"])
    registry.register(e1)
    registry.register(e2)
    
    vision_engines = registry.get_by_capability("vision")
    assert len(vision_engines) == 1
    assert vision_engines[0] == e1
    
    contrast_engines = registry.get_by_capability("contrast")
    assert len(contrast_engines) == 2
    
    struct_engines = registry.get_by_capability("structural")
    assert struct_engines[0] == e2

def test_registry_summaries(registry):
    e1 = MockEngine("e1")
    registry.register(e1)
    summaries = registry.get_engine_summaries()
    assert len(summaries) == 1
    assert summaries[0]["name"] == "e1"
    assert "capabilities" in summaries[0]

def test_registry_lifecycle_all(registry):
    e1 = MockEngine("e1")
    e2 = MockEngine("e2")
    registry.register(e1)
    registry.register(e2)
    
    registry.initialize_all()
    assert e1.initialized is True
    assert e2.initialized is True
    
    registry.shutdown_all()
    assert e1.shutdown_called is True
    assert e2.shutdown_called is True

def test_registry_validate_all(registry):
    e1 = MockEngine("e1")
    registry.register(e1)
    results = registry.validate_all()
    assert results["e1"] is True

def test_registry_clear(registry):
    registry.register(MockEngine("e1"))
    registry.clear()
    assert len(registry) == 0

def test_registry_iter_repr(registry):
    e1 = MockEngine("e1")
    registry.register(e1)
    engines = list(registry)
    assert engines[0] == e1
    assert "EngineRegistry" in repr(registry)
