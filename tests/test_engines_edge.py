# tests/test_engines_edge.py

import pytest
from app.engines.base import BaseAccessibilityEngine
from app.engines.registry import EngineRegistry

class TestEngineEdgeCases:
    """Test engine edge cases"""
    
    def test_base_engine(self):
        """Test base engine methods"""
        class TestEngine(BaseAccessibilityEngine):
            async def analyze(self, page_data, request):
                return []
            async def validate_config(self):
                return True
        
        engine = TestEngine("test", "1.0.0")
        assert engine.name == "test"
        assert engine.version == "1.0.0"
        assert engine.can_handle("anything") is False
        
        info = engine.get_info()
        assert info["name"] == "test"
        assert info["version"] == "1.0.0"
    
    def test_engine_registry(self):
        """Test engine registry operations"""
        registry = EngineRegistry()
        
        class TestEngine(BaseAccessibilityEngine):
            async def analyze(self, page_data, request):
                return []
            async def validate_config(self):
                return True
        
        engine = TestEngine("test", "1.0.0")
        
        # Register
        registry.register(engine)
        assert "test" in registry
        assert registry.count() == 1
        
        # Get
        assert registry.get("test") == engine
        assert registry.get("nonexistent") is None
        
        # Get all
        assert len(registry.get_all()) == 1
        
        # Unregister
        registry.unregister("test")
        assert registry.count() == 0
