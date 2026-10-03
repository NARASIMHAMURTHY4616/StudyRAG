"""Integration tests between Retriever, RAGPipeline, and DiagramService."""

from unittest.mock import MagicMock
from rag.pipeline import RAGPipeline
from visual_learning.diagram_service import DiagramService
from visual_learning.schemas import GroundingStatus


def test_rag_pipeline_visual_explanation_integration(tmp_path):
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = [
        {
            "document_name": "Networking_Course.pdf",
            "page_number": 105,
            "chunk_text": "The TCP handshake initiates reliable byte streams via SYN, SYN-ACK, ACK.",
            "score": 0.88,
        }
    ]

    mock_ollama = MagicMock()
    mock_ollama.generate.return_value = """{
        "title": "TCP 3-Way Handshake Workflow",
        "diagram_type": "sequenceDiagram",
        "explanation": "Client and server exchange SYN, SYN-ACK, ACK packets to establish reliable state.",
        "mermaid": "sequenceDiagram\\nClient->>Server: SYN\\nServer->>Client: SYN-ACK\\nClient->>Server: ACK"
    }"""

    pipeline = RAGPipeline(retriever=mock_retriever, ollama_client=mock_ollama)

    result = pipeline.generate_visual_explanation(
        question="Show TCP handshake diagram",
        top_k=2,
        min_similarity=0.3,
    )

    assert result["title"] == "TCP 3-Way Handshake Workflow"
    assert result["diagram_type"] == "sequenceDiagram"
    assert result["grounding_status"] == GroundingStatus.GROUNDED.value
    assert len(result["source_references"]) == 1
    assert result["source_references"][0]["document"] == "Networking_Course.pdf"
    assert result["source_references"][0]["page"] == 105
    assert "sequenceDiagram" in result["mermaid_code"]


def test_rag_pipeline_visual_explanation_no_context(tmp_path):
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = []

    mock_ollama = MagicMock()
    mock_ollama.generate.return_value = """{
        "title": "General Turing Machine",
        "diagram_type": "stateDiagram-v2",
        "explanation": "A conceptual Turing machine state transition.",
        "mermaid": "stateDiagram-v2\\n[*] --> q0\\nq0 --> q1: 1/0,R"
    }"""

    pipeline = RAGPipeline(retriever=mock_retriever, ollama_client=mock_ollama)

    result = pipeline.generate_visual_explanation(
        question="Diagram a Turing machine",
    )

    assert result["grounding_status"] == GroundingStatus.GENERAL_KNOWLEDGE.value
    assert result["source_references"] == []
    assert "stateDiagram-v2" in result["mermaid_code"]
