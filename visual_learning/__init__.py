"""StudyRAG V2.2 - Visual Learning Engine Package.

Provides local AI diagram generation (Mermaid), RAG-grounded visual explanations,
offline SVG/Mermaid export, and optional local AI image generation abstractions.
"""

from visual_learning.schemas import VisualArtifact, GroundingStatus, ValidationStatus
from visual_learning.diagram_service import DiagramService
from visual_learning.diagram_validator import DiagramValidator
from visual_learning.storage import VisualStorageManager
from visual_learning.image_service import ImageService
from visual_learning.image_backends import get_image_backend

__all__ = [
    "VisualArtifact",
    "GroundingStatus",
    "ValidationStatus",
    "DiagramService",
    "DiagramValidator",
    "VisualStorageManager",
    "ImageService",
    "get_image_backend",
]
