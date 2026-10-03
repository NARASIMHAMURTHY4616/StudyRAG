"""Unit tests for ingestion/text_cleaner.py and ingestion/chunker.py in V2."""

from ingestion.text_cleaner import clean_text
from ingestion.chunker import chunk_page, chunk_documents


def test_clean_text():
    dirty = "Hello   world!\r\n\r\nThis is a test of hy-\nphenation.\n\n\n\nNew paragraph."
    cleaned = clean_text(dirty)
    assert "hyphenation." in cleaned
    assert "\r" not in cleaned
    assert "\n\n\n" not in cleaned
    assert "Hello world!" in cleaned


def test_chunk_page_three_semantic_chunks():
    """Verify that a standard page produces approximately 3 semantic chunks with rich metadata."""
    paragraphs = [
        "First paragraph introducing operating system process management concepts and scheduling.",
        "Second paragraph explaining CPU burst cycles, I/O wait states, and context switching overhead.",
        "Third paragraph discussing priority inversion and real-time scheduling guarantees.",
        "Fourth paragraph discussing round robin time slices and multilevel feedback queues.",
    ]
    # Multiply to simulate full page content
    text = "\n\n".join(paragraphs * 4)
    page_data = {
        "source": "Operating Systems.pdf",
        "page": 25,
        "text": text,
    }

    chunks = chunk_page(page_data, target_chunks=3, overlap_words=20)
    assert len(chunks) == 3

    for idx, c in enumerate(chunks, start=1):
        assert c["document_name"] == "Operating Systems.pdf"
        assert c["source"] == "Operating Systems.pdf"
        assert c["page_number"] == 25
        assert c["page"] == 25
        assert c["chunk_index"] == idx
        assert "operating_systems_pdf_p0025_c" in c["chunk_id"]
        assert len(c["text"]) > 0
        assert c["chunk_text"] == c["text"]


def test_chunk_page_small_content():
    """Verify that very short page produces 1 coherent chunk."""
    page_data = {
        "source": "Cover.pdf",
        "page": 1,
        "text": "Chapter 1: Introduction to Distributed Systems",
    }
    chunks = chunk_page(page_data, target_chunks=3)
    assert len(chunks) == 1
    assert chunks[0]["page"] == 1
    assert "Chapter 1" in chunks[0]["text"]


def test_chunk_page_empty():
    page_data = {
        "source": "Empty.pdf",
        "page": 1,
        "text": "   ",
    }
    chunks = chunk_page(page_data)
    assert chunks == []


def test_chunk_documents_multi_page():
    pages = [
        {"source": "Doc.pdf", "page": 1, "text": "Page one paragraph 1.\n\nPage one paragraph 2.\n\nPage one paragraph 3. " * 5},
        {"source": "Doc.pdf", "page": 2, "text": "Page two paragraph 1.\n\nPage two paragraph 2.\n\nPage two paragraph 3. " * 5},
    ]
    chunks = chunk_documents(pages, target_chunks=3)
    assert len(chunks) >= 4
    page_1_chunks = [c for c in chunks if c["page"] == 1]
    page_2_chunks = [c for c in chunks if c["page"] == 2]
    assert len(page_1_chunks) >= 2
    assert len(page_2_chunks) >= 2

