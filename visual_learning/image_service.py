"""Image generation orchestration service for StudyRAG V2.2."""

import logging
from typing import Dict, Any, Optional

from config import settings
from visual_learning.schemas import ImageGenerationResult
from visual_learning.image_backends import ImageGenerationBackend, get_image_backend

logger = logging.getLogger(__name__)


class ImageService:
    """Service layer managing local educational illustration requests."""

    def __init__(self, backend: Optional[ImageGenerationBackend] = None):
        self.backend = backend or get_image_backend()

    def is_available(self) -> bool:
        """Check if active image backend is ready."""
        return self.backend.is_available()

    def get_status(self) -> Dict[str, Any]:
        """Get backend availability status."""
        return self.backend.get_status()

    def generate_illustration(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> ImageGenerationResult:
        """Attempt educational illustration generation."""
        query = prompt.strip() if prompt else ""
        if not query:
            return ImageGenerationResult(
                artifact_id="",
                status="error",
                error="Prompt cannot be empty.",
            )

        try:
            return self.backend.generate_image(
                prompt=query,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                seed=seed,
            )
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            return ImageGenerationResult(
                artifact_id="",
                status="error",
                error=f"Image generation failed: {e}",
            )
