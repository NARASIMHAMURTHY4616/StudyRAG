"""Local FAISS Vector Store with metadata persistence and document registry."""

import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import faiss

from config import settings

logger = logging.getLogger(__name__)


class LocalVectorStore:
    """
    Offline local vector store backed by FAISS IndexFlatIP (Cosine Similarity)
    and JSON metadata persistence.
    """

    def __init__(
        self,
        dimension: int = 384,
        index_file: Path = settings.VECTOR_INDEX_FILE,
        metadata_file: Path = settings.METADATA_FILE,
        registry_file: Path = settings.INDEXED_REGISTRY_FILE,
    ):
        self.dimension = dimension
        self.index_file = Path(index_file)
        self.metadata_file = Path(metadata_file)
        self.registry_file = Path(registry_file)

        self.index: Optional[faiss.Index] = None
        self.metadata: List[Dict[str, Any]] = []
        self.registry: Dict[str, Dict[str, Any]] = {}

        self.load()

    def count(self) -> int:
        """Return total number of vectors in the store."""
        if self.index is None:
            return 0
        return self.index.ntotal

    def add(self, vectors: np.ndarray, metadatas: List[Dict[str, Any]]) -> None:
        """
        Add embedding vectors and their corresponding chunk metadata to the store.

        Args:
            vectors: np.ndarray of shape (N, dimension) and dtype float32.
            metadatas: List of N metadata dicts corresponding to each vector.
        """
        if len(vectors) == 0 or len(metadatas) == 0:
            return

        if len(vectors) != len(metadatas):
            raise ValueError(f"Vector count ({len(vectors)}) != Metadata count ({len(metadatas)})")

        if vectors.dtype != np.float32:
            vectors = vectors.astype(np.float32)

        if self.index is None:
            actual_dim = vectors.shape[1]
            self.dimension = actual_dim
            # Inner Product index on L2-normalized vectors calculates Cosine Similarity directly
            self.index = faiss.IndexFlatIP(self.dimension)

        self.index.add(vectors)
        self.metadata.extend(metadatas)
        self.save()
        logger.info(f"Added {len(vectors)} vectors to FAISS store. Total count: {self.count()}")

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for top-K nearest neighbors using cosine similarity.

        Args:
            query_vector: np.ndarray of shape (1, dimension) or (dimension,) float32.
            top_k: Number of most similar chunks to retrieve.

        Returns:
            List of metadata dicts with 'score' (float) field representing cosine similarity.
        """
        if self.count() == 0 or self.index is None:
            logger.info("Search requested on empty vector store.")
            return []

        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        if query_vector.dtype != np.float32:
            query_vector = query_vector.astype(np.float32)

        # Retrieve up to top_k (bounded by available total vectors)
        k = min(top_k, self.count())
        distances, indices = self.index.search(query_vector, k)

        results: List[Dict[str, Any]] = []
        for score, idx in zip(distances[0], indices[0]):
            if idx == -1 or idx >= len(self.metadata):
                continue
            chunk_info = dict(self.metadata[idx])
            chunk_info["score"] = float(score)
            results.append(chunk_info)

        return results

    def is_document_indexed(self, filename: str, sha256_hash: str) -> bool:
        """Check if document has already been indexed with identical hash."""
        doc_entry = self.registry.get(filename)
        if not doc_entry:
            return False
        return doc_entry.get("hash") == sha256_hash

    def register_document(self, filename: str, sha256_hash: str, pages_count: int, chunks_count: int) -> None:
        """Register document hash and details into the document registry."""
        self.registry[filename] = {
            "hash": sha256_hash,
            "pages_count": pages_count,
            "chunks_count": chunks_count,
            "indexed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._save_registry()

    def remove_document(self, filename: str, all_vectors: Optional[np.ndarray] = None) -> None:
        """
        Remove chunks belonging to a specific document.
        Reconstructs the index from remaining vectors to preserve exact alignment with metadata.
        """
        if filename in self.registry:
            del self.registry[filename]
            self._save_registry()

        remaining_indices = [i for i, m in enumerate(self.metadata) if m.get("source") != filename]
        if len(remaining_indices) == len(self.metadata):
            return

        new_metadata = [self.metadata[i] for i in remaining_indices]

        if len(remaining_indices) == 0:
            self.clear()
            return

        # Extract vectors from FAISS index directly if not explicitly supplied
        if all_vectors is None and self.index is not None and self.index.ntotal >= len(self.metadata):
            try:
                all_vectors = self.index.reconstruct_n(0, len(self.metadata))
            except Exception as e:
                logger.warning(f"Could not reconstruct vectors from FAISS index: {e}")
                all_vectors = None

        if all_vectors is not None and len(remaining_indices) > 0:
            new_vectors = all_vectors[remaining_indices]
            self.index = faiss.IndexFlatIP(self.dimension)
            self.index.add(new_vectors)
            self.metadata = new_metadata
            self.save()
        else:
            self.metadata = new_metadata
            self.save()

    def save(self) -> None:
        """Persist FAISS index, metadata, and registry to disk."""
        try:
            settings.VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
            if self.index is not None and self.index.ntotal > 0:
                faiss.write_index(self.index, str(self.index_file))

            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2)

            self._save_registry()
            logger.info(f"Saved vector index ({self.count()} vectors) and metadata to {settings.VECTOR_DB_DIR}")
        except Exception as e:
            logger.error(f"Failed to persist vector store: {e}")
            raise

    def load(self) -> None:
        """Load FAISS index and metadata from disk if present."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    self.registry = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load document registry: {e}")
                self.registry = {}

        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load metadata file: {e}")
                self.metadata = []

        if self.index_file.exists():
            try:
                self.index = faiss.read_index(str(self.index_file))
                self.dimension = self.index.d
                logger.info(f"Loaded existing FAISS index with {self.index.ntotal} vectors (dim={self.dimension})")
                if len(self.metadata) != self.index.ntotal:
                    logger.warning(
                        f"Vector index count ({self.index.ntotal}) differs from metadata count ({len(self.metadata)}). "
                        "Index will use bounded lookups."
                    )
            except Exception as e:
                logger.warning(f"Could not load FAISS index file: {e}")
                self.index = None
        else:
            self.index = None

    def _save_registry(self) -> None:
        """Save registry mapping."""
        try:
            settings.VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(self.registry, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save registry: {e}")

    def clear(self) -> None:
        """Reset the vector store and clear files."""
        self.index = None
        self.metadata = []
        self.registry = {}
        if self.index_file.exists():
            self.index_file.unlink(missing_ok=True)
        if self.metadata_file.exists():
            self.metadata_file.unlink(missing_ok=True)
        if self.registry_file.exists():
            self.registry_file.unlink(missing_ok=True)
        logger.info("Vector store reset completely.")
