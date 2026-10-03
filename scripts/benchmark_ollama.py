"""Ollama Performance Benchmarking and Latency Diagnostics for StudyRAG V2."""

import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings
from core.ollama_client import OllamaClient
from core.prompts import build_rag_prompt
from retrieval.retriever import Retriever
from vectorstore.local_store import LocalVectorStore
from embeddings.embedder import Embedder


def run_benchmark_test(
    client: OllamaClient,
    test_name: str,
    prompt: str,
    description: str,
) -> Dict[str, Any]:
    """Execute a timed streaming test against Ollama and record metrics."""
    print(f"\n--- {test_name}: {description} ---")
    print(f"Prompt length: {len(prompt)} characters")

    t_start = time.perf_counter()
    first_token_time: Optional[float] = None
    tokens = []

    try:
        for token in client.generate_stream(prompt):
            if first_token_time is None:
                first_token_time = time.perf_counter() - t_start
            tokens.append(token)
    except Exception as e:
        print(f"Error during benchmark run: {e}")
        return {
            "test_name": test_name,
            "status": "error",
            "error": str(e),
        }

    total_time = time.perf_counter() - t_start
    full_text = "".join(tokens)
    generated_tokens = len(tokens)
    tok_sec = round(generated_tokens / (total_time - (first_token_time or 0)), 2) if (total_time - (first_token_time or 0)) > 0 else 0

    print(f"Time to first token (TTFT): {first_token_time:.3f}s" if first_token_time else "TTFT: N/A")
    print(f"Total time: {total_time:.3f}s")
    print(f"Generated tokens count: {generated_tokens}")
    print(f"Tokens/sec: {tok_sec}")
    print(f"Response preview:\n{full_text[:160].strip()}...")

    return {
        "test_name": test_name,
        "prompt_chars": len(prompt),
        "ttft_seconds": round(first_token_time or 0, 3),
        "total_time_seconds": round(total_time, 3),
        "generated_tokens": generated_tokens,
        "tokens_per_sec": tok_sec,
        "response_chars": len(full_text),
    }


def main():
    print("=" * 60)
    print(" StudyRAG V2 — Ollama Performance Benchmark ")
    print("=" * 60)

    client = OllamaClient()

    if not client.is_available():
        print(f"ERROR: Ollama is not running at {settings.OLLAMA_BASE_URL}.")
        print("Please start Ollama (`ollama serve`) and try again.")
        sys.exit(1)

    print(f"Target Model: {settings.OLLAMA_MODEL}")
    print(f"Base URL: {settings.OLLAMA_BASE_URL}")
    print(f"Think disabled (fast mode): {not settings.OLLAMA_THINK}")
    print(f"Max output tokens: {settings.MAX_OUTPUT_TOKENS}")
    print(f"Temperature: {settings.TEMPERATURE}")

    results = []

    # Test A — Tiny prompt
    test_a_prompt = "Say hello in one sentence."
    results.append(run_benchmark_test(client, "Test A (Tiny Prompt)", test_a_prompt, "Single sentence greeting"))

    # Test B — Academic direct prompt
    test_b_prompt = "Explain the four necessary conditions for deadlock."
    results.append(run_benchmark_test(client, "Test B (Academic Direct Prompt)", test_b_prompt, "Direct conceptual question"))

    # Test C — Grounded RAG-style prompt with actual retrieved chunks
    store = LocalVectorStore()
    embedder = Embedder()
    retriever = Retriever(embedder=embedder, vector_store=store)

    rag_query = "Explain the four necessary conditions for Deadlock and how to prevent them."
    retrieved_chunks = retriever.retrieve(rag_query, top_k=settings.TOP_K, min_similarity=settings.MIN_SIMILARITY)
    test_c_prompt = build_rag_prompt(question=rag_query, retrieved_chunks=retrieved_chunks)

    results.append(run_benchmark_test(client, "Test C (Grounded RAG Prompt)", test_c_prompt, f"RAG prompt with {len(retrieved_chunks)} retrieved chunks"))

    print("\n" + "=" * 60)
    print("=== Ollama Performance Summary ===")
    print(f"Model: {settings.OLLAMA_MODEL}")
    print("=" * 60)

    for r in results:
        print(f"\n{r['test_name']}")
        print(f"  Prompt chars: {r.get('prompt_chars')}")
        print(f"  Time to first token: {r.get('ttft_seconds')}s")
        print(f"  Total time: {r.get('total_time_seconds')}s")
        print(f"  Generated tokens: {r.get('generated_tokens')}")
        print(f"  Tokens/sec: {r.get('tokens_per_sec')}")
        print(f"  Response chars: {r.get('response_chars')}")

    print("\nBenchmark completed successfully.")


if __name__ == "__main__":
    main()
