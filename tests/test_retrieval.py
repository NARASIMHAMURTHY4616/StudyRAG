"""Unit tests for vector store, retriever, and RAG pipeline."""

import pytest
import numpy as np
from pathlib import Path
from vectorstore.local_store import LocalVectorStore
from embeddings.embedder import Embedder
from retrieval.retriever import Retriever
from rag.pipeline import RAGPipeline
from core.prompts import NO_CONTEXT_MESSAGE


@pytest.fixture
def temp_vector_store(tmp_path):
    """Create an isolated vector store in a temp directory."""
    idx_file = tmp_path / "test_index.bin"
    meta_file = tmp_path / "test_metadata.json"
    reg_file = tmp_path / "test_registry.json"
    store = LocalVectorStore(
        dimension=384,
        index_file=idx_file,
        metadata_file=meta_file,
        registry_file=reg_file,
    )
    return store


def test_vector_store_persistence(temp_vector_store, tmp_path):
    embedder = Embedder()
    chunks = [
        {"chunk_id": "os_001", "text": "Deadlock prevention eliminates circular wait.", "source": "OS.pdf", "page": 10},
        {"chunk_id": "os_002", "text": "Paging is a memory management scheme.", "source": "OS.pdf", "page": 20},
    ]
    texts = [c["text"] for c in chunks]
    vectors = embedder.embed_documents(texts)

    temp_vector_store.add(vectors, chunks)
    assert temp_vector_store.count() == 2

    # Load in new instance
    reloaded_store = LocalVectorStore(
        dimension=384,
        index_file=tmp_path / "test_index.bin",
        metadata_file=tmp_path / "test_metadata.json",
        registry_file=tmp_path / "test_registry.json",
    )
    assert reloaded_store.count() == 2
    assert len(reloaded_store.metadata) == 2


def test_retriever_similarity_and_ranking(temp_vector_store):
    embedder = Embedder()
    chunks = [
        {"chunk_id": "os_001", "text": "Deadlock happens when processes circularly wait for resources.", "source": "OS.pdf", "page": 15},
        {"chunk_id": "bio_001", "text": "Mitochondria is the powerhouse of the cell.", "source": "Bio.pdf", "page": 5},
    ]
    texts = [c["text"] for c in chunks]
    vectors = embedder.embed_documents(texts)
    temp_vector_store.add(vectors, chunks)

    retriever = Retriever(embedder=embedder, vector_store=temp_vector_store)

    # Deadlock query should match os_001 with high score and filter out bio_001 if threshold is high
    results = retriever.retrieve("Explain deadlock in operating systems", top_k=2, min_similarity=0.30)
    assert len(results) >= 1
    assert results[0]["chunk_id"] == "os_001"
    assert results[0]["page"] == 15
    assert results[0]["score"] > 0.40


def test_rag_no_context_behavior(temp_vector_store):
    embedder = Embedder()
    retriever = Retriever(embedder=embedder, vector_store=temp_vector_store)
    pipeline = RAGPipeline(retriever=retriever)

    # Empty store -> should return NO_CONTEXT_MESSAGE immediately
    res = pipeline.answer_question("What is quantum computing?")
    assert res["status"] == "no_context"
    assert res["answer"] == NO_CONTEXT_MESSAGE
    assert res["sources"] == []
