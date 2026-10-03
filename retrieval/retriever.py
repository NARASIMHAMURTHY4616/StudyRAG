"""Retriever for query vectorization and similarity-based chunk search (V2: Top-K=10)."""

import logging
from typing import List, Dict, Any, Optional
from config import settings
from embeddings.embedder import Embedder
from vectorstore.local_store import LocalVectorStore

logger = logging.getLogger(__name__)


class Retriever:
    """Retrieves relevant document chunks for a query using embedding similarity."""

    def __init__(
        self,
        embedder: Optional[Embedder] = None,
        vector_store: Optional[LocalVectorStore] = None,
    ):
        self.embedder = embedder or Embedder()
        self.vector_store = vector_store or LocalVectorStore()

    def retrieve(
        self,
        query: str,
        top_k: int = settings.TOP_K,
        min_similarity: float = settings.MIN_SIMILARITY,
    ) -> List[Dict[str, Any]]:
        """
        Embed a user query and retrieve top-K most similar chunks above min_similarity.

        Args:
            query: Natural language question.
            top_k: Number of candidates to retrieve (default 10).
            min_similarity: Threshold score [0.0 - 1.0]. Results below this are excluded.

        Returns:
            List of matching chunk dicts with normalized metadata fields:
            'score', 'text', 'chunk_text', 'document_name', 'source', 'page_number', 'page', 'chunk_id'.
        """
        query_str = query.strip()
        if not query_str:
            return []

        if self.vector_store.count() == 0:
            logger.info("Vector store is empty; 0 chunks retrieved.")
            return []

        logger.info(f"Retrieving top {top_k} chunks for query: '{query_str[:60]}...'")
        query_vec = self.embedder.embed_query(query_str)
        candidates = self.vector_store.search(query_vec, top_k=top_k)

        # Apply similarity threshold and normalize metadata keys
        filtered_chunks: List[Dict[str, Any]] = []
        for chunk in candidates:
            score = float(chunk.get("score", 0.0))
            if score >= min_similarity:
                doc_name = chunk.get("document_name") or chunk.get("source") or "Document"
                page_num = chunk.get("page_number") or chunk.get("page") or 1
                text_content = chunk.get("chunk_text") or chunk.get("text") or ""
                
                normalized = dict(chunk)
                normalized["document_name"] = doc_name
                normalized["source"] = doc_name
                normalized["page_number"] = page_num
                normalized["page"] = page_num
                normalized["chunk_text"] = text_content
                normalized["text"] = text_content
                normalized["score"] = round(score, 4)
                filtered_chunks.append(normalized)
            else:
                logger.debug(
                    f"Filtered out chunk {chunk.get('chunk_id')} (score: {score:.3f} < {min_similarity})"
                )

        logger.info(
            f"Retrieved {len(candidates)} candidates, {len(filtered_chunks)} passed threshold ({min_similarity:.2f})"
        )
        return filtered_chunks

