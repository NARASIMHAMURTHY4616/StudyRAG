"""Custom exceptions for StudyRAG V2.2 Visual Learning Engine."""


class VisualLearningError(Exception):
    """Base exception for all visual learning engine errors."""
    pass


class DiagramGenerationError(VisualLearningError):
    """Raised when diagram generation fails from model or timeout."""
    pass


class DiagramValidationError(VisualLearningError):
    """Raised when generated diagram fails syntax or security validation."""
    pass


class ImageBackendUnavailableError(VisualLearningError):
    """Raised when optional image generation backend is unavailable or not configured."""
    pass


class ImageGenerationError(VisualLearningError):
    """Raised when image generation process fails."""
    pass


class ArtifactNotFoundError(VisualLearningError):
    """Raised when requested visual artifact ID does not exist."""
    pass


class StorageSecurityError(VisualLearningError):
    """Raised when an unauthorized path traversal or unsafe file access is detected."""
    pass
