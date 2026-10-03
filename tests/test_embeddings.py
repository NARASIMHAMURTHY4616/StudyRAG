"""Unit tests for embeddings/embedder.py."""

import numpy as np
from embeddings.embedder import Embedder


def test_embedder_shapes_and_norm():
    embedder = Embedder()
    texts = [
        "Operating systems manage hardware resources.",
        "Deadlock occurs when processes hold locks and wait for others.",
    ]

    embeddings = embedder.embed_documents(texts)

    assert isinstance(embeddings, np.ndarray)
    assert embeddings.shape[0] == 2
    assert embeddings.shape[1] == embedder.dimension
    assert embeddings.dtype == np.float32

    # Verify L2 normalization (sum of squares ≈ 1.0)
    norms = np.linalg.norm(embeddings, axis=1)
    for norm in norms:
        assert np.isclose(norm, 1.0, atol=1e-3)


def test_embed_query():
    embedder = Embedder()
    query_vec = embedder.embed_query("What is deadlock?")
    assert query_vec.shape == (1, embedder.dimension)
    assert np.isclose(np.linalg.norm(query_vec), 1.0, atol=1e-3)
