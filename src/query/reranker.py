"""
Cross-Encoder Reranker

Reranks initial retrieval results using a cross-encoder model for higher precision.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class ResultReranker:
    """
    Reranks search results using a cross-encoder model.

    Cross-encoders jointly encode the query and document, producing
    more accurate relevance scores than bi-encoder cosine similarity.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None  # Lazy load

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.model_name)
                logger.info(f"Loaded cross-encoder: {self.model_name}")
            except ImportError:
                logger.error("sentence-transformers not installed")
                raise

    def rerank(self, query: str, results: list, top_k: int = 5) -> list:
        """
        Rerank results using cross-encoder scores.

        Args:
            query: The user query
            results: List of SearchResult objects
            top_k: Number of top results to return

        Returns:
            Reranked list of SearchResult objects
        """
        if not results:
            return results

        try:
            self._load_model()

            pairs = [(query, r.document) for r in results]
            scores = self._model.predict(pairs)

            # Attach reranker scores and sort
            scored = sorted(
                zip(scores, results),
                key=lambda x: x[0],
                reverse=True
            )

            reranked = []
            for score, result in scored[:top_k]:
                # Normalise score to [0, 1] range via sigmoid
                import math
                normalised = 1 / (1 + math.exp(-float(score)))
                result.score = normalised
                reranked.append(result)

            logger.debug(f"Reranked {len(results)} → {len(reranked)} results")
            return reranked

        except Exception as e:
            logger.warning(f"Reranking failed, returning original order: {e}")
            return results[:top_k]
