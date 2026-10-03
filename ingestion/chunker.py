"""Page-aware academic text chunking (V2: ~3 semantic chunks per page)."""

import re
import logging
from typing import List, Dict, Any, Optional
from config import settings
from ingestion.text_cleaner import clean_text

logger = logging.getLogger(__name__)


def _sanitize_id(text: str) -> str:
    """Create a clean, URL/file-safe identifier from filename."""
    return re.sub(r"[^a-zA-Z0-9_]+", "_", text).strip("_").lower()


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences while respecting common sentence terminators."""
    raw_sentences = re.split(r"(?<=[.?!])\s+", text)
    sentences = [s.strip() for s in raw_sentences if s.strip()]
    return sentences if sentences else ([text] if text.strip() else [])


def chunk_page(
    page_data: Dict[str, Any],
    target_chunks: int = settings.TARGET_CHUNKS_PER_PAGE,
    overlap_words: int = settings.CHUNK_OVERLAP,
) -> List[Dict[str, Any]]:
    """
    Chunk text from a single page into structured, semantic chunks (~3 chunks per page).

    Preserves semantic boundaries (paragraphs and sentences) rather than raw character cuts.

    Args:
        page_data: Dict containing "source" (or "document_name"), "page" (or "page_number"), and "text"
        target_chunks: Target number of chunks per page (default 3)
        overlap_words: Number of overlapping words between consecutive chunks

    Returns:
        List of chunk dicts containing full V2 and backward-compatible metadata:
            - chunk_id: Unique string id (e.g., "os_pdf_p0025_c001")
            - document_id: Sanitized doc id
            - document_name: Original document name
            - source: Original document name (V1 compatibility)
            - page_number: 1-indexed page number
            - page: 1-indexed page number (V1 compatibility)
            - chunk_index: 1, 2, 3...
            - text: Chunk content
            - chunk_text: Chunk content (V2 alias)
    """
    doc_name = page_data.get("document_name") or page_data.get("source") or "unknown_doc.pdf"
    page_num = page_data.get("page_number") or page_data.get("page") or 1
    raw_text = page_data.get("chunk_text") or page_data.get("text") or ""

    cleaned = clean_text(raw_text)
    if not cleaned:
        return []

    doc_id = _sanitize_id(doc_name)
    total_words = len(cleaned.split())

    # If page has very little content (< 40 words), return single chunk
    if total_words <= 40:
        chunk_id = f"{doc_id}_p{page_num:04d}_c001"
        return [{
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "document_name": doc_name,
            "source": doc_name,
            "page_number": page_num,
            "page": page_num,
            "chunk_index": 1,
            "text": cleaned,
            "chunk_text": cleaned,
        }]

    # Split page into atomic semantic units (paragraphs, sub-split into sentences if long)
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [cleaned]

    # Collect sentences / smaller units
    units: List[str] = []
    for p in paragraphs:
        p_sentences = _split_into_sentences(p)
        if p_sentences:
            units.extend(p_sentences)
        else:
            units.append(p)

    # Determine desired chunk count (target ~3 chunks, bounded by content length)
    if total_words < 120:
        desired_chunks = min(2, target_chunks)
    else:
        desired_chunks = target_chunks

    words_per_chunk = max(25, total_words // desired_chunks)

    # Distribute units across chunks respecting sentence boundaries and overlap
    chunks_data: List[Dict[str, Any]] = []
    current_unit_group: List[str] = []
    current_word_count = 0
    chunk_idx = 1

    for unit in units:
        u_words = len(unit.split())
        current_unit_group.append(unit)
        current_word_count += u_words

        # If current chunk has reached target size and we haven't created all desired chunks
        if current_word_count >= words_per_chunk and chunk_idx < desired_chunks:
            chunk_str = " ".join(current_unit_group).strip()
            if chunk_str:
                cid = f"{doc_id}_p{page_num:04d}_c{chunk_idx:03d}"
                chunks_data.append({
                    "chunk_id": cid,
                    "document_id": doc_id,
                    "document_name": doc_name,
                    "source": doc_name,
                    "page_number": page_num,
                    "page": page_num,
                    "chunk_index": chunk_idx,
                    "text": chunk_str,
                    "chunk_text": chunk_str,
                })
                chunk_idx += 1

            # Keep last sentences for overlap
            overlap_group: List[str] = []
            overlap_count = 0
            for prev_u in reversed(current_unit_group):
                pw = len(prev_u.split())
                if overlap_count + pw <= overlap_words or not overlap_group:
                    overlap_group.insert(0, prev_u)
                    overlap_count += pw
                else:
                    break
            current_unit_group = overlap_group
            current_word_count = overlap_count

    # Add final remaining group as the last chunk
    if current_unit_group:
        chunk_str = " ".join(current_unit_group).strip()
        if chunk_str:
            cid = f"{doc_id}_p{page_num:04d}_c{chunk_idx:03d}"
            chunks_data.append({
                "chunk_id": cid,
                "document_id": doc_id,
                "document_name": doc_name,
                "source": doc_name,
                "page_number": page_num,
                "page": page_num,
                "chunk_index": chunk_idx,
                "text": chunk_str,
                "chunk_text": chunk_str,
            })

    return chunks_data


def chunk_documents(
    pages: List[Dict[str, Any]],
    target_chunks: int = settings.TARGET_CHUNKS_PER_PAGE,
    overlap_words: int = settings.CHUNK_OVERLAP,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Chunk an entire list of pages extracted from documents.
    Preserves backward compatibility for callers specifying chunk_size/chunk_overlap.

    Returns:
        List of chunk dicts.
    """
    all_chunks: List[Dict[str, Any]] = []
    eff_overlap = chunk_overlap if chunk_overlap is not None else overlap_words

    for page_data in pages:
        page_chunks = chunk_page(
            page_data,
            target_chunks=target_chunks,
            overlap_words=eff_overlap,
        )
        all_chunks.extend(page_chunks)

    logger.info(f"Chunked {len(pages)} pages into {len(all_chunks)} total semantic chunks.")
    return all_chunks

