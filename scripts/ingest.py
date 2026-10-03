"""CLI Document Ingestion Script for StudyRAG."""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings
from ingestion.pdf_loader import load_pdf, compute_pdf_hash
from ingestion.chunker import chunk_documents
from embeddings.embedder import Embedder
from vectorstore.local_store import LocalVectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def ingest_file(
    pdf_path: Path,
    embedder: Embedder,
    vector_store: LocalVectorStore,
    force: bool = False,
) -> bool:
    """Ingest a single PDF file into the vector database."""
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        print(f"Skipping non-PDF file: {pdf_path}")
        return False

    filename = pdf_path.name
    print(f"\n==========================================")
    print(f"Processing PDF: {filename}")
    print(f"==========================================")

    # 1. Compute Hash
    file_hash = compute_pdf_hash(pdf_path)

    # 2. Check for Duplicates
    if not force and vector_store.is_document_indexed(filename, file_hash):
        print(f"Document '{filename}' already indexed with identical content.")
        print("Skipping.")
        return False

    # 3. Load PDF
    print(f"Loading PDF...")
    try:
        pages = load_pdf(pdf_path)
    except Exception as e:
        print(f"Failed to load PDF: {e}")
        return False

    total_pages = len(pages)
    print(f"Pages extracted: {total_pages}")
    if total_pages == 0:
        print(f"No readable text found in {filename}.")
        return False

    # 4. Create Chunks
    print(f"\nCreating semantic chunks (~{settings.TARGET_CHUNKS_PER_PAGE} chunks/page, overlap={settings.CHUNK_OVERLAP} words)...")
    chunks = chunk_documents(
        pages,
        target_chunks=settings.TARGET_CHUNKS_PER_PAGE,
        overlap_words=settings.CHUNK_OVERLAP,
    )
    total_chunks = len(chunks)
    print(f"Chunks created: {total_chunks}")
    if total_chunks == 0:
        print(f"No chunks generated from {filename}.")
        return False


    # 5. Generate Embeddings
    print(f"\nGenerating embeddings using '{embedder.model_name}'...")
    chunk_texts = [c["text"] for c in chunks]
    vectors = embedder.embed_documents(chunk_texts)

    # 6. Store in Vector Database
    print(f"\nSaving vector database...")
    # If re-indexing changed document, remove older version first
    if vector_store.is_document_indexed(filename, "") or filename in vector_store.registry:
        print(f"Document changed. Replacing previous index for '{filename}'...")
        vector_store.remove_document(filename)

    vector_store.add(vectors, chunks)
    vector_store.register_document(
        filename=filename,
        sha256_hash=file_hash,
        pages_count=total_pages,
        chunks_count=total_chunks,
    )

    print("\nIngestion complete.")
    print(f"Document: {filename}")
    print(f"Pages: {total_pages}")
    print(f"Chunks: {total_chunks}")
    print(f"Total Database Vectors: {vector_store.count()}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Ingest PDF study materials into StudyRAG")
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default=None,
        help="Path to specific PDF file to ingest. If omitted, scans data/documents/",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force re-indexing even if file hash matches",
    )
    args = parser.parse_args()

    settings.ensure_directories()
    embedder = Embedder()
    vector_store = LocalVectorStore()

    if args.pdf_path:
        target = Path(args.pdf_path)
        if not target.exists():
            print(f"Error: File '{target}' does not exist.")
            sys.exit(1)
        ingest_file(target, embedder, vector_store, force=args.force)
    else:
        doc_dir = settings.DOCUMENT_DIR
        pdf_files = list(doc_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in {doc_dir}.")
            print(f"Place PDFs inside '{doc_dir}' or specify a file path:")
            print(f"  python scripts/ingest.py path/to/document.pdf")
            return

        print(f"Found {len(pdf_files)} PDF(s) in {doc_dir}:")
        for p in pdf_files:
            print(f" - {p.name}")

        ingested_count = 0
        for pdf_file in sorted(pdf_files):
            success = ingest_file(pdf_file, embedder, vector_store, force=args.force)
            if success:
                ingested_count += 1

        print(f"\nAll ingestion tasks finished. Ingested {ingested_count}/{len(pdf_files)} PDFs.")


if __name__ == "__main__":
    main()
