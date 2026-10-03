"""Unit tests for Embedder model lifecycle and caching."""

import numpy as np
import pytest
from embeddings.embedder import Embedder
from config import settings


def test_embedder_singleton_reuse():
    e1 = Embedder()
    m1 = e1.model
    e2 = Embedder()
    m2 = e2.model

    # Both instances must share the same underlying model in memory
    assert m1 is m2
    assert e1.dimension == 384
    assert e2.dimension == 384


def test_embed_query_normalization():
    embedder = Embedder()
    vec = embedder.embed_query("Deadlock in operating systems")

    assert isinstance(vec, np.ndarray)
    assert vec.shape == (1, 384)
    assert vec.dtype == np.float32

    # Vector should be normalized to unit length (L2 norm == 1.0)
    norm = np.linalg.norm(vec[0])
    assert pytest.approx(norm, 0.001) == 1.0


def test_embed_empty_query():
    embedder = Embedder()
    with pytest.raises(ValueError):
        embedder.embed_query("   ")
