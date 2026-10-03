"""Optional Local AI Image Generation Backends for StudyRAG V2.2.

Provides an extensible, decoupled abstraction for local text-to-image backends.
Does NOT download large models automatically and does NOT assume Ollama or Qwen3:1.7B is an image model.
"""

import abc
import uuid
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from config import settings
from visual_learning.schemas import ImageGenerationResult

logger = logging.getLogger(__name__)


class ImageGenerationBackend(abc.ABC):
    """Abstract interface for local educational illustration image backends."""

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Check whether required local dependencies and model weights are installed."""
        pass

    @abc.abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Return human-readable backend diagnostic status."""
        pass

    @abc.abstractmethod
    def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> ImageGenerationResult:
        """Generate an educational illustration image from prompt."""
        pass


class NullImageBackend(ImageGenerationBackend):
    """Default inactive backend when no local text-to-image model is configured."""

    def is_available(self) -> bool:
        return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "backend": "none",
            "available": False,
            "enabled": settings.VISUAL_IMAGE_GENERATION_ENABLED,
            "message": (
                "Local AI Image Generation is currently optional and disabled. "
                "Technical diagram generation (Mermaid flowcharts, sequence diagrams, "
                "state machines) remains fully functional without GPU or external models."
            ),
        }

    def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> ImageGenerationResult:
        return ImageGenerationResult(
            artifact_id=str(uuid.uuid4()),
            status="unavailable",
            backend="none",
            error=(
                "Local image generation backend is not configured or disabled. "
                "Use technical diagram generation for offline architectural charts."
            ),
        )


class LocalDiffusersBackend(ImageGenerationBackend):
    """
    Extensible backend for local PyTorch/Diffusers pipelines.
    Never downloads models during import or initialization.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or os.getenv("DIFFUSERS_MODEL_PATH", "")

    def is_available(self) -> bool:
        """Check if torch and diffusers packages exist and local weights are present."""
        if not settings.VISUAL_IMAGE_GENERATION_ENABLED:
            return False
        try:
            import torch  # noqa: F401
            import diffusers  # noqa: F401
            if self.model_path and Path(self.model_path).exists():
                return True
        except ImportError:
            pass
        return False

    def get_status(self) -> Dict[str, Any]:
        available = self.is_available()
        return {
            "backend": "diffusers",
            "available": available,
            "enabled": settings.VISUAL_IMAGE_GENERATION_ENABLED,
            "model_path": self.model_path,
            "message": "Local diffusers backend ready." if available else "Diffusers framework or local model weights not found.",
        }

    def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> ImageGenerationResult:
        if not self.is_available():
            return ImageGenerationResult(
                artifact_id=str(uuid.uuid4()),
                status="unavailable",
                backend="diffusers",
                error="Local diffusers backend is not available.",
            )

        # Conservative dimensions for modest hardware (8 GB RAM / CPU)
        w = width or 512
        h = height or 512
        artifact_id = str(uuid.uuid4())

        # Placeholder simulation for concrete mock testing
        return ImageGenerationResult(
            artifact_id=artifact_id,
            status="disabled",
            backend="diffusers",
            error="Diffusers model execution requires explicit local weights directory configuration.",
        )


def get_image_backend(backend_name: Optional[str] = None) -> ImageGenerationBackend:
    """Factory to instantiate the configured image generation backend."""
    name = (backend_name or settings.IMAGE_GENERATION_BACKEND).lower()

    if name == "diffusers":
        return LocalDiffusersBackend()
    return NullImageBackend()
