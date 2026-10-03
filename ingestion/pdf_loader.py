"""PDF Loader using PyMuPDF for structured, page-aware text extraction."""

import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Union
import pymupdf as fitz

logger = logging.getLogger(__name__)


def compute_pdf_hash(file_path: Union[str, Path]) -> str:
    """Compute SHA-256 hash of a PDF file to detect duplicates or modifications."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {path}")

    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_pdf(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Open a PDF and extract text on a per-page basis.

    Args:
        file_path: Path to the PDF file.

    Returns:
        List of dictionaries with keys:
            - "source": Name of the PDF file (basename)
            - "page": 1-indexed page number
            - "text": Raw extracted text from that page
    """
    path = Path(file_path)
    if not path.exists():
        logger.error(f"Cannot load PDF: File does not exist at {path}")
        raise FileNotFoundError(f"File not found: {path}")

    filename = path.name
    pages_data: List[Dict[str, Any]] = []

    logger.info(f"Opening PDF: {filename} ({path})")
    try:
        doc = fitz.open(path)
    except Exception as e:
        logger.error(f"Failed to open/parse PDF {filename}: {e}")
        raise ValueError(f"Corrupted or invalid PDF file '{filename}': {e}") from e

    try:
        total_pages = len(doc)
        if total_pages == 0:
            logger.warning(f"PDF {filename} contains 0 pages.")
            return []

        logger.info(f"Extracting text from {total_pages} pages in {filename}...")

        for page_idx in range(total_pages):
            page_num = page_idx + 1  # 1-indexed for human / academic citation
            try:
                page = doc.load_page(page_idx)
                text = page.get_text("text") or ""
                pages_data.append({
                    "source": filename,
                    "page": page_num,
                    "text": text,
                })
            except Exception as e:
                logger.warning(f"Error reading page {page_num} of {filename}: {e}. Skipping page text.")
                pages_data.append({
                    "source": filename,
                    "page": page_num,
                    "text": "",
                })

        logger.info(f"Successfully extracted {len(pages_data)} pages from {filename}.")
        return pages_data

    finally:
        doc.close()
