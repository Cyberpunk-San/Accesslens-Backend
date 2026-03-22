
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..models.schemas import UnifiedIssue, AuditRequest

class BaseAccessibilityEngine(ABC):


    def __init__(self, name: str, version: str):

        self.name = name
        self.version = version
        self.capabilities = []

    @abstractmethod
    async def analyze(
        self,
        page_data: Dict[str, Any],
        request: AuditRequest
    ) -> List[UnifiedIssue]:

        pass

    @abstractmethod
    async def validate_config(self) -> bool:

        pass

    def can_handle(self, capability: str) -> bool:

        return capability in self.capabilities

    async def initialize(self) -> None:

        pass

    async def shutdown(self) -> None:

        pass

    def get_info(self) -> Dict[str, Any]:

        return {
            "name": self.name,
            "version": self.version,
            "capabilities": self.capabilities,
            "class": self.__class__.__name__
        }

    def __repr__(self) -> str:

        return f"{self.__class__.__name__}(name={self.name}, version={self.version})"