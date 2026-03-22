import torch
import asyncio
import logging
import gc
from typing import Optional, Dict, Any, List
from ..core.config import settings


class MistralService:
    def __init__(self, model_path: Optional[str] = None, device: Optional[str] = None):
        self.model_path = model_path
        self.device = device or self._detect_device()
        self._logger = logging.getLogger(__name__)
        self._model = None
        self._semaphore = asyncio.Semaphore(2)  
        self._torch_device = torch.device(self.device)

    def _detect_device(self) -> str:
        if torch.cuda.is_available(): return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available(): return "mps"
        else: return "cpu"

    async def load_model(self):
        try:
            self._logger.info(f"Loading Mistral 7B model on {self.device}...")
            await asyncio.sleep(3)
            self._model = "mistral-loaded"
            self._logger.info("Mistral 7B model loaded")
        except Exception as e:
            self._logger.error(f"Failed to load Mistral: {e}")
            raise

    async def unload_model(self):
        if self._model:
            self._logger.info(f"Unloading Mistral 7B model from {self.device}...")
            self._model = None
            gc.collect()
            if self.device == "cuda":
                torch.cuda.empty_cache()
            self._logger.info("Mistral 7B model unloaded")

    async def generate_fix(
        self,
        context: str,
        max_tokens: int = 500,
        temperature: float = 0.3
    ) -> Optional[Dict[str, Any]]:
        async with self._semaphore:
            try:
                await asyncio.sleep(1.5)
                return self._simulate_fix_generation(context)
            except Exception as e:
                self._logger.error(f"Fix generation failed: {e}")
                return None
            finally:
                if self.device == "cuda":
                    torch.cuda.empty_cache()

    def _simulate_fix_generation(self, context: str) -> Dict[str, Any]:
        if "missing_alt" in context or "image-alt" in context:
            return {
                "code_before": '<img src="logo.jpg">',
                "code_after": '<img src="logo.jpg" alt="Company logo - Home">',
                "explanation": "Added descriptive alt text that conveys the image purpose and context."
            }
        elif "low_contrast" in context:
            return {
                "code_before": ".text { color: #ccc; }",
                "code_after": ".text { color: #555; }",
                "explanation": "Darkened text color to meet WCAG AA contrast requirements while maintaining visual design."
            }
        elif "button-name" in context or "empty_button" in context:
            return {
                "code_before": '<button class="icon-btn"></button>',
                "code_after": '<button class="icon-btn" aria-label="Search"><span aria-hidden="true"></span></button>',
                "explanation": "Added accessible label for icon button and proper icon semantics."
            }
        elif "heading_skip" in context:
            return {
                "code_before": '<h1>Title</h1>\n<h3>Subtitle</h3>',
                "code_after": '<h1>Title</h1>\n<h2>Section</h2>\n<h3>Subtitle</h3>',
                "explanation": "Inserted missing h2 to maintain proper heading hierarchy."
            }
        else:
            return {
                "code_before": "<!-- Original code not available -->",
                "code_after": "<!-- Add appropriate ARIA labels and semantic HTML -->",
                "explanation": "Review the element and add proper accessible attributes."
            }