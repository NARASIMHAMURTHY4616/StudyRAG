"""Unit tests for VisualStorageManager, sanitize_svg, and path traversal defenses."""

import pytest
from pathlib import Path
from visual_learning.storage import VisualStorageManager, sanitize_svg, is_safe_identifier
from visual_learning.schemas import VisualArtifact
from visual_learning.exceptions import ArtifactNotFoundError, StorageSecurityError


def test_sanitize_svg_strips_scripts_and_events():
    malicious_svg = """<svg width="100" height="100" onload="alert('pwned')">
        <script>fetch('/steal-cookies')</script>
        <circle cx="50" cy="50" r="40" onclick="evilCode()"/>
        <a href="javascript:void(0)"><text>Click</text></a>
    </svg>"""

    clean_svg = sanitize_svg(malicious_svg)
    assert "<script>" not in clean_svg
    assert "onload" not in clean_svg
    assert "onclick" not in clean_svg
    assert "javascript:" not in clean_svg
    assert "<circle" in clean_svg


def test_storage_save_and_retrieve_artifact(tmp_path):
    storage = VisualStorageManager(base_dir=tmp_path)
    artifact = VisualArtifact(
        artifact_id="art-test-12345678",
        title="Test Diagram",
        prompt="Test prompt",
        mermaid_code="flowchart TD\nA-->B",
    )

    saved = storage.save_artifact(artifact)
    assert saved.artifact_id == "art-test-12345678"

    loaded = storage.get_artifact("art-test-12345678")
    assert loaded.title == "Test Diagram"
    assert loaded.mermaid_code == "flowchart TD\nA-->B"


def test_storage_not_found(tmp_path):
    storage = VisualStorageManager(base_dir=tmp_path)
    with pytest.raises(ArtifactNotFoundError):
        storage.get_artifact("non-existent-artifact-id")


def test_storage_path_traversal_prevention(tmp_path):
    storage = VisualStorageManager(base_dir=tmp_path)

    with pytest.raises(StorageSecurityError):
        storage.get_artifact("../../../etc/passwd")

    with pytest.raises(StorageSecurityError):
        storage.save_svg_export("../evil_dir/evil", "<svg><circle/></svg>")


def test_storage_save_svg_export(tmp_path):
    storage = VisualStorageManager(base_dir=tmp_path)
    svg_content = '<svg viewBox="0 0 100 100"><rect width="100" height="100"/></svg>'

    svg_path = storage.save_svg_export("safe-artifact-id-123", svg_content)
    assert svg_path.exists()
    assert svg_path.name == "safe-artifact-id-123.svg"

    retrieved_path = storage.get_svg_export_path("safe-artifact-id-123")
    assert retrieved_path == svg_path
