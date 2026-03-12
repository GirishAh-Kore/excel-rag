"""
Query Expander

Implements HyDE (Hypothetical Document Embeddings) and synonym expansion
to improve retrieval recall.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class QueryExpander:
    """
    Expands queries using HyDE and synonym generation.

    HyDE: Ask the LLM to generate a hypothetical answer document, then
    embed that document instead of (or alongside) the raw query. This
    bridges the vocabulary gap between short queries and long documents.
    """

    def __init__(self, llm_service):
        """
        Args:
            llm_service: LLMService used for HyDE generation
        """
        self.llm_service = llm_service

    def expand_with_hyde(self, query: str) -> str:
        """
        Generate a hypothetical answer document for the query.

        Args:
            query: Original user query

        Returns:
            Hypothetical document text to use as the search embedding
        """
        system_prompt = (
            "You are an expert on Excel financial data. "
            "Write a short, factual passage (2-4 sentences) that would directly answer "
            "the following question if it appeared in an Excel spreadsheet context. "
            "Be specific and use domain-appropriate language."
        )
        try:
            hypothetical = self.llm_service.generate(
                prompt=query,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=150
            )
            logger.debug(f"HyDE expansion generated ({len(hypothetical)} chars)")
            return hypothetical
        except Exception as e:
            logger.warning(f"HyDE expansion failed, using original query: {e}")
            return query

    def expand_with_synonyms(self, query: str) -> List[str]:
        """
        Generate synonym/paraphrase variants of the query.

        Args:
            query: Original user query

        Returns:
            List of query variants (including the original)
        """
        system_prompt = (
            "Generate 3 concise alternative phrasings of the following question "
            "that preserve the original meaning. Return one per line, no numbering."
        )
        try:
            result = self.llm_service.generate(
                prompt=query,
                system_prompt=system_prompt,
                temperature=0.5,
                max_tokens=120
            )
            variants = [line.strip() for line in result.strip().splitlines() if line.strip()]
            return [query] + variants[:3]
        except Exception as e:
            logger.warning(f"Synonym expansion failed: {e}")
            return [query]
