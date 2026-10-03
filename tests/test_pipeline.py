"""Unit tests for RAG pipeline, context building, and prompt generation in V2."""

from core.prompts import build_rag_prompt, NO_CONTEXT_MESSAGE
from rag.pipeline import RAGPipeline, extract_images_from_text


def test_build_rag_prompt_with_history():
    history = [
        {"role": "user", "content": "What is an Operating System?"},
        {"role": "assistant", "content": "An OS manages computer hardware and software resources."},
    ]
    chunks = [
        {"document_name": "OS.pdf", "page_number": 12, "chunk_text": "Kernel is the central core of an OS."},
        {"document_name": "OS.pdf", "page_number": 13, "chunk_text": "Process control block contains CPU registers."},
    ]

    prompt = build_rag_prompt(
        question="Explain the role of the kernel",
        retrieved_chunks=chunks,
        conversation_history=history,
    )

    assert "Recent Conversation History:" in prompt
    assert "Student: What is an Operating System?" in prompt
    assert "Study Material (Retrieved Context):" in prompt
    assert "OS.pdf (Page 12)" in prompt
    assert "Kernel is the central core" in prompt
    assert "Current Question:\nExplain the role of the kernel" in prompt


def test_extract_images_from_text():
    text_with_md_image = "Here is the diagram: ![Process States](/static/images/process_states.png) and explanation."
    imgs = extract_images_from_text(text_with_md_image)
    assert len(imgs) == 1
    assert imgs[0] == "/static/images/process_states.png"

    text_with_html_image = 'Look at <img src="/static/diagrams/tcp.jpg" alt="TCP"/>.'
    imgs2 = extract_images_from_text(text_with_html_image)
    assert len(imgs2) == 1
    assert imgs2[0] == "/static/diagrams/tcp.jpg"

    no_image_text = "Just standard text without any images."
    assert extract_images_from_text(no_image_text) == []
