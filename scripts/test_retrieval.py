"""Interactive CLI Retrieval Debugging Tool for StudyRAG."""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings
from retrieval.retriever import Retriever
from vectorstore.local_store import LocalVectorStore
from embeddings.embedder import Embedder


def main():
    print("==========================================")
    print("StudyRAG Interactive Retrieval Debugger")
    print("Test retrieval results and similarity scores")
    print("==========================================")

    store = LocalVectorStore()
    if store.count() == 0:
        print("\nWarning: Vector database is empty!")
        print("Please ingest some PDFs first using: python scripts/ingest.py\n")

    embedder = Embedder()
    retriever = Retriever(embedder=embedder, vector_store=store)

    print(f"Embedding Model: {settings.EMBEDDING_MODEL}")
    print(f"Indexed Vectors: {store.count()}")
    print(f"Default Top-K: {settings.TOP_K}")
    print(f"Default Min Similarity: {settings.MIN_SIMILARITY}")
    print("\nType your question/query below (or 'exit' / 'quit' to stop):\n")

    while True:
        try:
            query = input("Enter query > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if not query:
            continue

        if query.lower() in ["exit", "quit", "q"]:
            print("Goodbye!")
            break

        print(f"\nSearching for top {settings.TOP_K} chunks (min_similarity >= {settings.MIN_SIMILARITY})...")
        results = retriever.retrieve(query, top_k=settings.TOP_K, min_similarity=settings.MIN_SIMILARITY)

        if not results:
            print("\nNo relevant chunks found above similarity threshold.")
            print(f"Threshold: {settings.MIN_SIMILARITY}\n")
            continue

        print(f"\nRetrieved {len(results)} chunks:\n")
        for i, chunk in enumerate(results, start=1):
            score = chunk.get("score", 0.0)
            source = chunk.get("source", "Unknown")
            page = chunk.get("page", "?")
            chunk_id = chunk.get("chunk_id", "N/A")
            text = chunk.get("text", "")

            print(f"[{i}] Score: {score:.4f} | Chunk: {chunk_id}")
            print(f"    Source: {source} (Page {page})")
            print("    Text:")
            for line in text.split("\n"):
                print(f"      {line}")
            print("-" * 50)
        print()


if __name__ == "__main__":
    main()
