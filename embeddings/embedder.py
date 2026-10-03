"""Local Sentence Transformers Embedder with singleton caching and offline loading."""

import os
import logging
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from config import settings

logger = logging.getLogger(__name__)


class Embedder:
    """CPU-friendly local embedding generator with shared process-level model cache."""

    _cached_model: Optional[SentenceTransformer] = None
    _cached_model_name: Optional[str] = None
    _cached_dimension: Optional[int] = None

    def __init__(
        self,
        model_name: str = settings.EMBEDDING_MODEL,
        batch_size: int = settings.EMBEDDING_BATCH_SIZE,
    ):
        self.model_name = model_name
        self.batch_size = batch_size

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load or return process-level cached SentenceTransformer model instance."""
        if Embedder._cached_model is None or Embedder._cached_model_name != self.model_name:
            if settings.OFFLINE_MODE:
                os.environ["TRANSFORMERS_OFFLINE"] = "1"
                os.environ["HF_HUB_OFFLINE"] = "1"

            logger.info(f"Loading local embedding model: '{self.model_name}' on CPU (Offline: {settings.OFFLINE_MODE})...")
            try:
                # Attempt strictly local load first if offline
                if settings.OFFLINE_MODE:
                    try:
                        Embedder._cached_model = SentenceTransformer(
                            self.model_name,
                            device="cpu",
                            local_files_only=True,
                        )
                    except Exception as offline_err:
                        logger.warning(f"Strict local_files_only load failed ({offline_err}), falling back to default loader.")
                        Embedder._cached_model = SentenceTransformer(self.model_name, device="cpu")
                else:
                    Embedder._cached_model = SentenceTransformer(self.model_name, device="cpu")

                Embedder._cached_model_name = self.model_name
                logger.info(f"Loaded '{self.model_name}' successfully. Embedding model: local | Network required: no")
            except Exception as e:
                logger.error(f"Failed to load embedding model '{self.model_name}': {e}")
                raise

        return Embedder._cached_model

    @property
    def dimension(self) -> int:
        """Return the vector dimensionality of the embedding model."""
        if Embedder._cached_dimension is None:
            if hasattr(self.model, "get_embedding_dimension"):
                Embedder._cached_dimension = self.model.get_embedding_dimension()
            else:
                Embedder._cached_dimension = self.model.get_sentence_embedding_dimension()
        return Embedder._cached_dimension

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        """
        Compute normalized embeddings for a list of document texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            np.ndarray of shape (len(texts), dimension) with float32 dtype.
        """
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        logger.info(f"Generating embeddings for {len(texts)} chunks in batches of {self.batch_size}...")
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,  # Enables exact Cosine Similarity via Inner Product
            convert_to_numpy=True,
        )

        return embeddings.astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        """
        Compute normalized embedding for a single user query.

        Args:
            text: Query string.

        Returns:
            np.ndarray of shape (1, dimension) with float32 dtype.
        """
        if not text.strip():
            raise ValueError("Query text cannot be empty.")

        embedding = self.model.encode(
            [text],
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return embedding.astype(np.float32)
