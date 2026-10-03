"""CLI Chunk Inspection Tool for StudyRAG."""

import sys
import argparse
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from vectorstore.local_store import LocalVectorStore


def main():
    parser = argparse.ArgumentParser(description="Inspect chunks stored in StudyRAG vector store")
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default=None,
        help="Filter chunks by source filename",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=20,
        help="Maximum number of chunks to display (default 20)",
    )
    parser.add_argument(
        "--search",
        "-q",
        type=str,
        default=None,
        help="Keyword search inside chunk text",
    )
    args = parser.parse_args()

    store = LocalVectorStore()
    total_chunks = len(store.metadata)

    print("==========================================")
    print(f"StudyRAG Chunk Inspector")
    print(f"Total Chunks in DB: {total_chunks}")
    print(f"Total Registered Documents: {len(store.registry)}")
    print("==========================================")

    if store.registry:
        print("\nRegistered Documents:")
        for doc_name, info in store.registry.items():
            print(f"  • {doc_name}: {info.get('pages_count', '?')} pages, {info.get('chunks_count', '?')} chunks (Indexed: {info.get('indexed_at', '?')})")
        print()

    if total_chunks == 0:
        print("No chunks found in database. Ingest documents first using `python scripts/ingest.py`.")
        return

    filtered = store.metadata
    if args.source:
        filtered = [c for c in filtered if args.source.lower() in c.get("source", "").lower()]
    if args.search:
        filtered = [c for c in filtered if args.search.lower() in c.get("text", "").lower()]

    print(f"Displaying {min(len(filtered), args.limit)} of {len(filtered)} matching chunks:\n")

    for idx, chunk in enumerate(filtered[:args.limit], start=1):
        chunk_id = chunk.get("chunk_id", "N/A")
        source = chunk.get("source", "N/A")
        page = chunk.get("page", "N/A")
        text = chunk.get("text", "")
        word_count = len(text.split())
        char_count = len(text)

        preview = text[:300] + ("..." if len(text) > 300 else "")

        print(f"[{idx}] Chunk ID: {chunk_id}")
        print(f"    Source: {source} | Page: {page}")
        print(f"    Stats:  {word_count} words ({char_count} characters)")
        print(f"    Text Preview:")
        print(f"    {preview}")
        print("-" * 50)


if __name__ == "__main__":
    main()
