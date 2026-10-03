"""Schemas and data models for StudyRAG V2.2 Visual Learning Engine."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone


class GroundingStatus(str, Enum):
    """Grounding status of the visual explanation against retrieved documents."""
    GROUNDED = "grounded"
    GENERAL_KNOWLEDGE = "general_knowledge"
    UNVALIDATED = "unvalidated"
    FAILED = "failed"


class ValidationStatus(str, Enum):
    """Validation status of generated Mermaid diagram code."""
    VALID = "valid"
    REPAIRED = "repaired"
    INVALID = "invalid"


class ArtifactType(str, Enum):
    """Type of generated visual artifact."""
    DIAGRAM = "diagram"
    ILLUSTRATION = "illustration"


@dataclass
class VisualArtifact:
    """Represents a generated visual artifact (Mermaid diagram or AI illustration)."""
    artifact_id: str
    title: str
    prompt: str
    artifact_type: str = ArtifactType.DIAGRAM.value
    diagram_type: str = "flowchart"
    mermaid_code: str = ""
    explanation: str = ""
    grounding_status: str = GroundingStatus.GENERAL_KNOWLEDGE.value
    source_references: List[Dict[str, Any]] = field(default_factory=list)
    validation_status: str = ValidationStatus.VALID.value
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_message: Optional[str] = None
    image_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    backend: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisualArtifact":
        """Safely create VisualArtifact from dictionary, ignoring unknown keys."""
        if not isinstance(data, dict):
            raise ValueError("Expected dictionary for VisualArtifact instantiation.")
        mermaid_code = data.get("mermaid_code") or data.get("mermaid") or ""
        valid_keys = {
            "artifact_id", "title", "prompt", "artifact_type", "diagram_type",
            "mermaid_code", "explanation", "grounding_status", "source_references",
            "validation_status", "created_at", "error_message", "image_path",
            "width", "height", "backend", "metadata"
        }
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        if "mermaid_code" not in filtered or not filtered["mermaid_code"]:
            filtered["mermaid_code"] = mermaid_code
        return cls(**filtered)

    def to_dict(self) -> Dict[str, Any]:
        """Convert artifact to clean dictionary for JSON serialization."""
        d = asdict(self)
        d["success"] = self.validation_status != ValidationStatus.INVALID.value and bool(self.mermaid_code)
        d["mermaid"] = self.mermaid_code
        return d


@dataclass
class ImageGenerationResult:
    """Result of an image generation attempt."""
    artifact_id: str
    status: str  # "success", "unavailable", "disabled", "error"
    image_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    output_format: str = "png"
    backend: str = "none"
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return asdict(self)
