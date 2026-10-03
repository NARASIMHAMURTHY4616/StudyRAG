"""Unit tests for ingestion/pdf_loader.py."""

import pytest
from pathlib import Path
import pymupdf as fitz
from ingestion.pdf_loader import load_pdf, compute_pdf_hash


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a temporary multi-page PDF for testing."""
    pdf_path = tmp_path / "operating_systems_test.pdf"
    doc = fitz.open()

    # Page 1
    p1 = doc.new_page()
    p1.insert_text((50, 50), "Chapter 1: Process Synchronization.\nDeadlock is a serious condition.")

    # Page 2 (Empty)
    p2 = doc.new_page()

    # Page 3
    p3 = doc.new_page()
    p3.insert_text((50, 50), "Chapter 2: Memory Management.\nVirtual memory enables paging.")

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_load_pdf_success(sample_pdf):
    pages = load_pdf(sample_pdf)
    assert len(pages) == 3
    assert pages[0]["source"] == "operating_systems_test.pdf"
    assert pages[0]["page"] == 1
    assert "Process Synchronization" in pages[0]["text"]

    # Page 2 is empty
    assert pages[1]["page"] == 2
    assert pages[1]["text"].strip() == ""

    # Page 3
    assert pages[2]["page"] == 3
    assert "Virtual memory" in pages[2]["text"]


def test_compute_pdf_hash(sample_pdf):
    h1 = compute_pdf_hash(sample_pdf)
    assert isinstance(h1, str)
    assert len(h1) == 64  # SHA-256 length

    h2 = compute_pdf_hash(sample_pdf)
    assert h1 == h2


def test_load_pdf_nonexistent():
    with pytest.raises(FileNotFoundError):
        load_pdf("/non/existent/path/doc.pdf")
