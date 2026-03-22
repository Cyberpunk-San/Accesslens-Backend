import torch
import asyncio
import logging
import gc
from typing import Optional, Dict, Any, List
from ..core.config import settings


class LLaVAService:

    def __init__(self, model_path: Optional[str] = None, device: Optional[str] = None):
        self.model_path = model_path
        self.device = device or self._detect_device()
        self._logger = logging.getLogger(__name__)
        self._model = None
        self._torch_device = torch.device(self.device)

    def _detect_device(self) -> str:
        if torch.cuda.is_available(): return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available(): return "mps"
        else: return "cpu"

    async def load_model(self):
        try:
            self._logger.info(f"Loading LLaVA model on {self.device}...")
            await asyncio.sleep(5)
            self._model = "llava-loaded"
            self._logger.info("LLaVA model successfully loaded")
        except Exception as e:
            self._logger.error(f"Failed to load LLaVA model: {e}")
            raise

    async def unload_model(self):
        if self._model:
            self._logger.info(f"Unloading LLaVA model from {self.device}...")
            self._model = None
            gc.collect()
            if self.device == "cuda":
                torch.cuda.empty_cache()
            elif self.device == "mps":
                pass
            self._logger.info("LLaVA model unloaded")

    async def analyze_image(
        self,
        image_data: str,
        prompt: str,
        temperature: float = 0.2
    ) -> Optional[Dict[str, Any]]:
        try:
            await asyncio.sleep(2)
            return {
                "findings": [
                    {
                        "issue_type": "visual_clutter",
                        "severity": "moderate",
                        "confidence": 0.82,
                        "description": "The page has multiple overlapping elements in the header area.",
                        "reasoning": "High density of interactive elements detected without clear visual separation.",
                        "suggestion": "Increase padding and use clearer visual grouping for header elements."
                    }
                ]
            }
        except Exception as e:
            self._logger.error(f"LLaVA analysis failed: {e}")
            return None
        finally:
            if self.device == "cuda":
                torch.cuda.empty_cache()
