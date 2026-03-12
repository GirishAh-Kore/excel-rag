"""
Context Compressor

Extracts only the query-relevant portions of retrieved documents
to reduce noise and token usage in the generation step.
"""

import logging

logger = logging.getLogger(__name__)


class ContextualCompressor:
    """
    Compresses retrieved document chunks to only the parts relevant to the query.

    Uses the LLM to extract the most relevant sentences/values, keeping
    the context window lean and focused.
    """

    def __init__(self, llm_service, max_tokens: int = 400):
        """
        Args:
            llm_service: LLMService for compression
            max_tokens: Approximate token budget for compressed output
        """
        self.llm_service = llm_service
        self.max_tokens = max_tokens

    def compress(self, query: str, document: str) -> str:
        """
        Extract the query-relevant portion of a document.

        Args:
            query: User query
            document: Full retrieved document text

        Returns:
            Compressed document text
        """
        # Skip compression for short documents
        if len(document.split()) <= 80:
            return document

        system_prompt = (
            "You are a precise information extractor. "
            "Given a question and a document excerpt, extract ONLY the sentences, "
            "values, or rows that are directly relevant to answering the question. "
            "Preserve exact numbers and dates. Be concise."
        )
        prompt = f"Question: {query}\n\nDocument:\n{document}\n\nRelevant excerpt:"

        try:
            compressed = self.llm_service.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.0,
                max_tokens=self.max_tokens
            )
            logger.debug(
                f"Compressed document {len(document.split())} → {len(compressed.split())} words"
            )
            return compressed.strip()
        except Exception as e:
            logger.warning(f"Context compression failed, using original: {e}")
            return document
