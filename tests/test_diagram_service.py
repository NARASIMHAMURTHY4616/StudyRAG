"""Unit tests for DiagramService (grounding, bounded repair, artifact creation)."""

from unittest.mock import MagicMock
import pytest

from visual_learning.diagram_service import DiagramService
from visual_learning.schemas import GroundingStatus, ValidationStatus
from visual_learning.storage import VisualStorageManager


def test_diagram_service_grounded_generation(tmp_path):
    storage = VisualStorageManager(base_dir=tmp_path)
    mock_ollama = MagicMock()
    mock_ollama.generate.return_value = """{
        "title": "OS Process States",
        "diagram_type": "stateDiagram-v2",
        "explanation": "Processes transition between New, Ready, Running, Waiting, and Terminated states.",
        "mermaid": "stateDiagram-v2\\n[*] --> New\\nNew --> Ready\\nReady --> Running\\nRunning --> Terminated"
    }"""

    service = DiagramService(ollama_client=mock_ollama, storage_manager=storage)

    chunks = [
        {"document_name": "OS_Notes.pdf", "page_number": 42, "chunk_text": "Process states in modern OS.", "score": 0.85}
    ]

    artifact = service.generate_diagram(
        question="Diagram OS Process States",
        retrieved_chunks=chunks,
    )

    assert artifact.title == "OS Process States"
    assert artifact.diagram_type == "stateDiagram-v2"
    assert artifact.grounding_status == GroundingStatus.GROUNDED.value
    assert artifact.validation_status == ValidationStatus.VALID.value
    assert len(artifact.source_references) == 1
    assert artifact.source_references[0]["document"] == "OS_Notes.pdf"
    assert artifact.source_references[0]["page"] == 42


def test_diagram_service_general_knowledge_when_no_chunks(tmp_path):
    storage = VisualStorageManager(base_dir=tmp_path)
    mock_ollama = MagicMock()
    mock_ollama.generate.return_value = """{
        "title": "Generic Flowchart",
        "diagram_type": "flowchart",
        "explanation": "General knowledge flow.",
        "mermaid": "flowchart TD\\nA --> B"
    }"""

    service = DiagramService(ollama_client=mock_ollama, storage_manager=storage)

    artifact = service.generate_diagram(
        question="Show a flowchart",
        retrieved_chunks=[],
    )

    assert artifact.grounding_status == GroundingStatus.GENERAL_KNOWLEDGE.value
    assert artifact.source_references == []
    assert artifact.validation_status == ValidationStatus.VALID.value


def test_diagram_service_bounded_repair_success(tmp_path):
    storage = VisualStorageManager(base_dir=tmp_path)
    mock_ollama = MagicMock()

    # First call returns invalid syntax (unclosed bracket)
    # Second call (repair attempt) returns valid syntax
    mock_ollama.generate.side_effect = [
        """{
            "title": "Broken Diagram",
            "diagram_type": "flowchart",
            "explanation": "Attempt 1",
            "mermaid": "flowchart TD\\nA[Unclosed --> B"
        }""",
        """{
            "title": "Repaired Diagram",
            "diagram_type": "flowchart",
            "explanation": "Repaired correctly",
            "mermaid": "flowchart TD\\nA[Fixed] --> B[Target]"
        }"""
    ]

    service = DiagramService(ollama_client=mock_ollama, storage_manager=storage)

    artifact = service.generate_diagram(
        question="Draw process flowchart",
        retrieved_chunks=None,
    )

    assert mock_ollama.generate.call_count == 2
    assert artifact.validation_status == ValidationStatus.REPAIRED.value
    assert "A[Fixed]" in artifact.mermaid_code


def test_diagram_service_empty_prompt_raises(tmp_path):
    storage = VisualStorageManager(base_dir=tmp_path)
    service = DiagramService(storage_manager=storage)

    with pytest.raises(ValueError, match="cannot be empty"):
        service.generate_diagram(question="   ")


def test_diagram_service_ollama_failure_raises(tmp_path):
    storage = VisualStorageManager(base_dir=tmp_path)
    mock_ollama = MagicMock()
    mock_ollama.generate.side_effect = RuntimeError("Ollama connection refused")

    service = DiagramService(ollama_client=mock_ollama, storage_manager=storage)

    with pytest.raises(Exception) as exc_info:
        service.generate_diagram(question="Draw a diagram")
    assert "generation failed" in str(exc_info.value).lower()

