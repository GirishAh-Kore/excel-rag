"""
Hybrid Searcher

Combines BM25 keyword search with semantic vector search using
Reciprocal Rank Fusion (RRF) for improved retrieval.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class HybridSearcher:
    """
    Merges BM25 and semantic search results via Reciprocal Rank Fusion.

    RRF score = sum(1 / (k + rank_i)) where k=60 is a smoothing constant.
    """

    def __init__(self, k: int = 60):
        """
        Args:
            k: RRF smoothing constant (default 60 per the original paper)
        """
        self.k = k

    def build_bm25_index(self, documents: List[str]):
        """
        Build a BM25 index from a list of document strings.

        Args:
            documents: Tokenised document corpus

        Returns:
            BM25Okapi index
        """
        try:
            from rank_bm25 import BM25Okapi
            tokenised = [doc.lower().split() for doc in documents]
            return BM25Okapi(tokenised)
        except ImportError:
            logger.error("rank-bm25 not installed. Run: pip install rank-bm25")
            raise

    def search(
        self,
        query: str,
        semantic_results: list,
        documents: List[str],
        top_k: int = 10
    ) -> list:
        """
        Merge semantic results with BM25 scores via RRF.

        Args:
            query: User query string
            semantic_results: Ordered list of SearchResult from vector search
            documents: Raw document texts matching semantic_results order
            top_k: Number of results to return

        Returns:
            Merged and re-ranked list of SearchResult objects
        """
        if not semantic_results:
            return semantic_results

        try:
            bm25 = self.build_bm25_index(documents)
            bm25_scores = bm25.get_scores(query.lower().split())

            # Build RRF scores
            rrf_scores: Dict[int, float] = {}

            # Semantic ranks
            for rank, result in enumerate(semantic_results):
                idx = rank  # index aligns with documents list
                rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (self.k + rank + 1)

            # BM25 ranks (sort indices by score descending)
            bm25_ranked = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
            for rank, idx in enumerate(bm25_ranked):
                rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (self.k + rank + 1)

            # Sort by combined RRF score
            sorted_indices = sorted(rrf_scores.keys(), key=lambda i: rrf_scores[i], reverse=True)

            merged = []
            for idx in sorted_indices[:top_k]:
                if idx < len(semantic_results):
                    result = semantic_results[idx]
                    result.score = min(rrf_scores[idx] * 10, 1.0)  # normalise loosely
                    merged.append(result)

            logger.debug(f"Hybrid search merged {len(semantic_results)} results → {len(merged)}")
            return merged

        except Exception as e:
            logger.warning(f"Hybrid search failed, falling back to semantic only: {e}")
            return semantic_results[:top_k]
