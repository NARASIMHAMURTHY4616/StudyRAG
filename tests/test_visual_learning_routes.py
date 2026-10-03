"""Integration and route tests for Visual Learning Engine API endpoints."""

import json
from unittest.mock import patch, MagicMock
import pytest
from app import app
from visual_learning.schemas import VisualArtifact, GroundingStatus, ValidationStatus


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_visualize_status_endpoint(client):
    res = client.get("/api/visualize/status")
    assert res.status_code == 200
    data = res.get_json()
    assert "visual_learning_enabled" in data
    assert "mermaid_available" in data
    assert "supported_diagram_types" in data
    assert "flowchart" in data["supported_diagram_types"]
    assert "sequencediagram" in data["supported_diagram_types"]


def test_visualize_missing_prompt(client):
    res = client.post("/api/visualize", json={})
    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data


@patch("rag.pipeline.RAGPipeline.generate_visual_explanation")
def test_visualize_success(mock_gen, client):
    mock_gen.return_value = {
        "artifact_id": "test-artifact-001",
        "title": "TCP Handshake",
        "diagram_type": "sequenceDiagram",
        "mermaid_code": "sequenceDiagram\nClient->>Server: SYN",
        "explanation": "Client sends SYN",
        "grounding_status": "general_knowledge",
        "source_references": [],
        "validation_status": "valid",
    }

    res = client.post("/api/visualize", json={"question": "Draw TCP Handshake"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["artifact_id"] == "test-artifact-001"
    assert data["title"] == "TCP Handshake"
    assert data["diagram_type"] == "sequenceDiagram"


def test_visualize_export_svg_endpoint(client):
    res = client.post("/api/visualize/export/svg", json={
        "artifact_id": "art-export-12345",
        "svg": '<svg width="200" height="100"><rect/></svg>'
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["artifact_id"] == "art-export-12345"

    # Now download the exported SVG
    dl_res = client.get("/api/visualize/export/art-export-12345")
    assert dl_res.status_code == 200
    assert "image/svg+xml" in dl_res.content_type
    assert b"<rect/>" in dl_res.data


def test_visualize_image_endpoint(client):
    res = client.post("/api/visualize/image", json={"prompt": "Illustrate operating system"})
    assert res.status_code == 200
    data = res.get_json()
    assert "status" in data
    assert data["status"] in ("unavailable", "disabled", "error")
