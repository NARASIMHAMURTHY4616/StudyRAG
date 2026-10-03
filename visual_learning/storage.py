"""Secure artifact storage, metadata persistence, and SVG sanitization for StudyRAG V2.2."""

import os
import re
import json
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from config import settings
from visual_learning.schemas import VisualArtifact
from visual_learning.exceptions import ArtifactNotFoundError, StorageSecurityError

logger = logging.getLogger(__name__)


def is_safe_identifier(identifier: str) -> bool:
    """Validate that artifact ID or filename is strictly alphanumeric/dashes/underscores."""
    if not identifier or not isinstance(identifier, str):
        return False
    return bool(re.match(r"^[a-zA-Z0-9_-]{8,64}$", identifier))


def sanitize_svg(svg_content: str) -> str:
    """
    Sanitize SVG markup by stripping script elements, active event attributes,
    and dangerous entity references.
    """
    if not svg_content:
        return ""

    sanitized = svg_content

    # Remove script tags
    sanitized = re.sub(r"<\s*script[^>]*>[\s\S]*?<\s*/\s*script\s*>", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"<\s*script[^>]*/>", "", sanitized, flags=re.IGNORECASE)

    # Remove dangerous elements
    sanitized = re.sub(r"<\s*(?:iframe|object|embed|applet|meta|link)[^>]*>", "", sanitized, flags=re.IGNORECASE)

    # Remove inline event attributes (e.g. onload, onclick, onerror)
    sanitized = re.sub(r"\bon\w+\s*=\s*[\"'][^\"']*[\"']", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bon\w+\s*=\s*[^>\s]+", "", sanitized, flags=re.IGNORECASE)

    # Remove javascript: and data: urls in href/src
    sanitized = re.sub(r"href\s*=\s*[\"']javascript:[^\"']*[\"']", "href=\"#\"", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"xlink:href\s*=\s*[\"']javascript:[^\"']*[\"']", "xlink:href=\"#\"", sanitized, flags=re.IGNORECASE)

    return sanitized.strip()


class VisualStorageManager:
    """Manages secure storage, retrieval, and export of visual artifacts and metadata."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = (base_dir or settings.GENERATED_VISUALS_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, filename: str) -> Path:
        """Resolve path and assert it is strictly within self.base_dir to prevent path traversal."""
        target = (self.base_dir / filename).resolve()
        try:
            target.relative_to(self.base_dir)
        except ValueError as e:
            raise StorageSecurityError(f"Path traversal detected for filename: '{filename}'") from e
        return target

    def save_artifact(self, artifact: VisualArtifact) -> VisualArtifact:
        """Save artifact metadata to JSON in base directory."""
        if not is_safe_identifier(artifact.artifact_id):
            artifact.artifact_id = str(uuid.uuid4())

        file_path = self._resolve_safe_path(f"{artifact.artifact_id}.json")
        data = artifact.to_dict()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved visual artifact '{artifact.artifact_id}' to {file_path}")
        return artifact

    def get_artifact(self, artifact_id: str) -> VisualArtifact:
        """Retrieve an existing artifact by unique identifier."""
        if not is_safe_identifier(artifact_id):
            raise StorageSecurityError(f"Invalid or unsafe artifact identifier: '{artifact_id}'")

        file_path = self._resolve_safe_path(f"{artifact_id}.json")
        if not file_path.exists():
            raise ArtifactNotFoundError(f"Visual artifact '{artifact_id}' not found.")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return VisualArtifact.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to read artifact '{artifact_id}': {e}")
            raise ArtifactNotFoundError(f"Could not read artifact '{artifact_id}': {e}") from e

    def save_svg_export(self, artifact_id: str, raw_svg: str) -> Path:
        """Sanitize and save rendered SVG file for export."""
        if not is_safe_identifier(artifact_id):
            raise StorageSecurityError(f"Invalid artifact identifier: '{artifact_id}'")

        cleaned_svg = sanitize_svg(raw_svg)
        if not cleaned_svg.startswith("<svg") and not "<svg" in cleaned_svg:
            raise ValueError("Invalid SVG markup provided.")

        svg_path = self._resolve_safe_path(f"{artifact_id}.svg")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(cleaned_svg)

        logger.info(f"Saved sanitized SVG export for '{artifact_id}' at {svg_path}")
        return svg_path

    def get_svg_export_path(self, artifact_id: str) -> Optional[Path]:
        """Get path to exported SVG file if it exists."""
        if not is_safe_identifier(artifact_id):
            return None
        svg_path = self._resolve_safe_path(f"{artifact_id}.svg")
        return svg_path if svg_path.exists() else None

    def list_artifacts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recently created visual artifacts."""
        artifacts: List[Dict[str, Any]] = []
        try:
            files = sorted(self.base_dir.glob("*.json"), key=os.path.getmtime, reverse=True)
            for file_path in files[:limit]:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        artifacts.append({
                            "artifact_id": data.get("artifact_id"),
                            "title": data.get("title"),
                            "diagram_type": data.get("diagram_type"),
                            "grounding_status": data.get("grounding_status"),
                            "created_at": data.get("created_at"),
                        })
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error listing artifacts: {e}")
        return artifacts
