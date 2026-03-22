
from typing import Dict, List, Optional, Type
import logging
from .base import BaseAccessibilityEngine

class EngineRegistry:


    def __init__(self):
        self._engines: Dict[str, BaseAccessibilityEngine] = {}
        self._logger = logging.getLogger(__name__)

    def register(self, engine: BaseAccessibilityEngine) -> None:

        if engine.name in self._engines:
            self._logger.warning(f"Engine {engine.name} already registered. Overwriting.")
        
        self._engines[engine.name] = engine
        self._logger.debug(f"Registered engine: {engine.name} v{engine.version}")

    def unregister(self, engine_name: str) -> None:

        if engine_name in self._engines:
            del self._engines[engine_name]
            self._logger.debug(f"Unregistered engine: {engine_name}")

    def get(self, engine_name: str) -> Optional[BaseAccessibilityEngine]:

        return self._engines.get(engine_name)

    def get_all(self) -> List[BaseAccessibilityEngine]:

        return list(self._engines.values())

    def get_by_capability(self, capability: str) -> List[BaseAccessibilityEngine]:

        return [
            engine for engine in self._engines.values()
            if engine.can_handle(capability)
        ]

    def get_engine_names(self) -> List[str]:

        return list(self._engines.keys())

    def get_engine_summaries(self) -> List[Dict[str, any]]:

        return [
            {
                "name": engine.name,
                "version": engine.version,
                "capabilities": engine.capabilities,
                "description": engine.__class__.__doc__ or "No description"
            }
            for engine in self._engines.values()
        ]

    def clear(self) -> None:

        self._engines.clear()
        self._logger.debug("Registry cleared")

    def count(self) -> int:

        return len(self._engines)

    def validate_all(self) -> Dict[str, bool]:

        results = {}
        for name, engine in self._engines.items():
            try:
                results[name] = engine.validate_config()
            except Exception as e:
                self._logger.error(f"Validation failed for {name}: {e}")
                results[name] = False
        return results

    def initialize_all(self) -> Dict[str, bool]:

        results = {}
        for name, engine in self._engines.items():
            if hasattr(engine, 'initialize') and callable(engine.initialize):
                try:
                    engine.initialize()
                    results[name] = True
                    self._logger.info(f"Initialized engine: {name}")
                except Exception as e:
                    self._logger.error(f"Failed to initialize {name}: {e}")
                    results[name] = False
        return results

    def shutdown_all(self) -> None:

        for name, engine in self._engines.items():
            if hasattr(engine, 'shutdown') and callable(engine.shutdown):
                try:
                    engine.shutdown()
                    self._logger.info(f"Shutdown engine: {name}")
                except Exception as e:
                    self._logger.error(f"Failed to shutdown {name}: {e}")

    def __contains__(self, engine_name: str) -> bool:

        return engine_name in self._engines

    def __iter__(self):

        return iter(self._engines.values())

    def __len__(self) -> int:

        return len(self._engines)

    def __repr__(self) -> str:

        return f"EngineRegistry(engines={list(self._engines.keys())})"