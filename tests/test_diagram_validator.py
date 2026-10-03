"""Unit tests for DiagramValidator (Mermaid parsing, sanitization, syntax validation)."""

import pytest
from visual_learning.diagram_validator import DiagramValidator, ALLOWED_DIAGRAM_TYPES


def test_strip_markdown_fences():
    text_with_json_fence = "```json\n{\"mermaid\": \"flowchart TD\\nA-->B\"}\n```"
    assert DiagramValidator.strip_markdown_fences(text_with_json_fence) == "{\"mermaid\": \"flowchart TD\\nA-->B\"}"

    text_with_mermaid_fence = "```mermaid\nsequenceDiagram\nClient->>Server: SYN\n```"
    assert DiagramValidator.strip_markdown_fences(text_with_mermaid_fence) == "sequenceDiagram\nClient->>Server: SYN"

    plain_text = "flowchart LR\nStart --> End"
    assert DiagramValidator.strip_markdown_fences(plain_text) == "flowchart LR\nStart --> End"


def test_sanitize_mermaid_text():
    unsafe_script = "flowchart TD\nA[<script>alert('xss')</script>Node] --> B"
    sanitized = DiagramValidator.sanitize_mermaid_text(unsafe_script)
    assert "<script>" not in sanitized
    assert "alert" not in sanitized
    assert "A[Node] --> B" in sanitized or "A[] --> B" in sanitized or "Node" in sanitized

    unsafe_event = 'A["<div onclick=\'exploit()\'>Text</div>"]'
    sanitized_event = DiagramValidator.sanitize_mermaid_text(unsafe_event)
    assert "onclick" not in sanitized_event


def test_parse_model_response_json():
    json_response = """
    {
        "title": "TCP 3-Way Handshake",
        "diagram_type": "sequenceDiagram",
        "explanation": "Client sends SYN, server responds with SYN-ACK, client ACKs.",
        "mermaid": "sequenceDiagram\\nClient->>Server: SYN\\nServer->>Client: SYN-ACK\\nClient->>Server: ACK"
    }
    """
    parsed = DiagramValidator.parse_model_response(json_response)
    assert parsed["title"] == "TCP 3-Way Handshake"
    assert parsed["diagram_type"] == "sequenceDiagram"
    assert "Client->>Server: SYN" in parsed["mermaid"]
    assert "SYN-ACK" in parsed["explanation"]


def test_parse_model_response_markdown_fallback():
    markdown_response = """Here is the flowchart for CPU scheduling:

```mermaid
flowchart TD
ReadyQueue --> CPU
CPU --> Terminated
```

This represents standard FCFS scheduling."""
    parsed = DiagramValidator.parse_model_response(markdown_response)
    assert parsed["diagram_type"] == "flowchart"
    assert "ReadyQueue --> CPU" in parsed["mermaid"]
    assert "FCFS scheduling" in parsed["explanation"]


def test_validate_mermaid_syntax_valid():
    valid_flowchart = """flowchart TD
    A[Start] --> B{Is Valid?}
    B -- Yes --> C[Process]
    B -- No --> D[End]
    C --> D"""
    is_valid, sanitized, errors = DiagramValidator.validate_mermaid_syntax(valid_flowchart)
    assert is_valid is True
    assert len(errors) == 0
    assert "A[Start]" in sanitized


def test_validate_mermaid_syntax_mismatched_brackets():
    invalid_code = "flowchart TD\nA[Start --> B(End"
    is_valid, sanitized, errors = DiagramValidator.validate_mermaid_syntax(invalid_code)
    assert is_valid is False
    assert any("Mismatched delimiters" in e for e in errors)


def test_validate_mermaid_syntax_missing_header():
    no_header = "A[Start] --> B[End]"
    is_valid, sanitized, errors = DiagramValidator.validate_mermaid_syntax(no_header)
    assert is_valid is False
    assert any("declaration header" in e for e in errors)


def test_validate_mermaid_syntax_empty():
    is_valid, sanitized, errors = DiagramValidator.validate_mermaid_syntax("")
    assert is_valid is False
    assert any("empty" in e.lower() for e in errors)


def test_normalize_mermaid_source_escaped_newlines():
    escaped = "flowchart TD\\nA[Start] --> B[End]\\nB --> C[Done]"
    normalized = DiagramValidator.normalize_mermaid_source(escaped)
    assert "\n" in normalized
    assert "\\n" not in normalized
    assert "A[Start] --> B[End]" in normalized


def test_parse_model_response_truncated_json():
    # Model response truncated before closing quote and bracket
    truncated = '{\n  "title": "Memory Chip Architecture",\n  "diagram_type": "flowchart LR",\n  "explanation": "Illustrates memory chip.",\n  "mermaid": "flowchart LR\\nInput --> Decoder\\nDecoder --> MemoryCell'
    parsed = DiagramValidator.parse_model_response(truncated)
    assert parsed["is_parsed"] is True
    assert parsed["title"] == "Memory Chip Architecture"
    assert "flowchart LR" in parsed["mermaid"]
    assert "Input --> Decoder" in parsed["mermaid"]
    assert parsed["explanation"] == "Illustrates memory chip."


def test_parse_model_response_failed_json_does_not_dump_raw_json_in_explanation():
    malformed = '{"title": "Broken", "invalid_field": 123'
    parsed = DiagramValidator.parse_model_response(malformed)
    assert parsed["is_parsed"] is False
    assert parsed["mermaid"] == ""
    # Explanation must not be the raw JSON string
    assert not parsed["explanation"].startswith("{")
    assert parsed["error"] is not None

