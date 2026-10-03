"""Unit tests for prompt construction, context budgeting, and query enrichment."""

from core.prompts import build_rag_prompt, enrich_query_with_history, SYSTEM_PROMPT


def test_build_rag_prompt_source_metadata_preservation():
    chunks = [
        {
            "document_name": "Operating_Systems.pdf",
            "page_number": 16,
            "chunk_text": "Mutual Exclusion is condition 1.",
        },
        {
            "document_name": "Operating_Systems.pdf",
            "page_number": 17,
            "chunk_text": "Hold and Wait is condition 2.",
        },
    ]

    prompt = build_rag_prompt(
        question="Explain deadlock conditions",
        retrieved_chunks=chunks,
    )

    assert "Operating_Systems.pdf" in prompt
    assert "Page: 16" in prompt
    assert "Mutual Exclusion is condition 1." in prompt
    assert "Page: 17" in prompt
    assert "Hold and Wait is condition 2." in prompt
    assert "Explain deadlock conditions" in prompt


def test_build_rag_prompt_context_budgeting():
    # Create large chunks exceeding max_context_chars
    chunks = [
        {"document_name": f"Doc_{i}.pdf", "page_number": i, "chunk_text": "A" * 500}
        for i in range(10)
    ]

    # Budget of 1200 chars should only include ~2 chunks without crashing or splitting
    prompt = build_rag_prompt(
        question="What is this?",
        retrieved_chunks=chunks,
        max_context_chars=1200,
    )

    assert "Doc_0.pdf" in prompt
    assert "Doc_1.pdf" in prompt
    # Later chunks should be cut off by budget
    assert "Doc_9.pdf" not in prompt


def test_build_rag_prompt_history_limit():
    history = [
        {"role": "user", "content": f"Question {i}"}
        for i in range(10)
    ]

    prompt = build_rag_prompt(
        question="Latest question",
        retrieved_chunks=[],
        conversation_history=history,
        max_history_turns=3,
    )

    # Only last 3 turns should appear
    assert "Question 9" in prompt
    assert "Question 8" in prompt
    assert "Question 7" in prompt
    assert "Question 1" not in prompt


def test_enrich_query_with_history():
    history = [
        {"role": "user", "content": "Explain deadlock prevention methods"},
        {"role": "assistant", "content": "Deadlock prevention involves removing one of the 4 conditions."},
    ]

    enriched = enrich_query_with_history("what about the second condition?", history)
    assert "deadlock" in enriched.lower() or "prevention" in enriched.lower()
