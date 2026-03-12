"""
Query Classifier Module for Smart Excel Query Pipeline.

This module implements intelligent query classification using keyword-based
pattern matching and LLM fallback for ambiguous cases. It classifies queries
into types (aggregation, lookup, summarization, comparison) and extracts
relevant parameters like aggregation functions, filters, and column references.

Key Components:
- QueryClassifier: Main class for classifying queries
- ClassifierConfig: Configuration for classification behavior
- LLMServiceProtocol: Protocol for LLM service dependency
- EmbeddingServiceProtocol: Protocol for embedding service dependency

Supports Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from src.exceptions import ClassificationError
from src.models.query_pipeline import QueryClassification, QueryType

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class ClassifierConfig:
    """
    Configuration for QueryClassifier.
    
    Attributes:
        confidence_threshold: Threshold below which LLM is used (default 0.6).
        alternative_threshold: Threshold for including alternative types (default 0.6).
        max_alternatives: Maximum number of alternative types to return (default 2).
        use_llm_fallback: Whether to use LLM for ambiguous cases (default True).
        llm_temperature: Temperature for LLM classification (default 0.1).
        llm_max_tokens: Max tokens for LLM response (default 500).
    """
    confidence_threshold: float = 0.6
    alternative_threshold: float = 0.6
    max_alternatives: int = 2
    use_llm_fallback: bool = True
    llm_temperature: float = 0.1
    llm_max_tokens: int = 500
    
    def __post_init__(self) -> None:
        """Validate configuration values."""
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError(
                f"confidence_threshold must be 0-1, got {self.confidence_threshold}"
            )
        
        if not 0.0 <= self.alternative_threshold <= 1.0:
            raise ValueError(
                f"alternative_threshold must be 0-1, got {self.alternative_threshold}"
            )
        
        if self.max_alternatives < 0:
            raise ValueError(
                f"max_alternatives must be >= 0, got {self.max_alternatives}"
            )


# =============================================================================
# Protocols (Dependency Injection Interfaces)
# =============================================================================


@runtime_checkable
class LLMServiceProtocol(Protocol):
    """
    Protocol for LLM service dependency.
    
    Implementations must provide methods for generating text and
    structured responses.
    """
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Generate text completion for a prompt.
        
        Args:
            prompt: User prompt/question.
            system_prompt: Optional system instructions.
            temperature: Sampling temperature (0.0 to 1.0).
            max_tokens: Maximum tokens to generate.
            
        Returns:
            Generated text response.
        """
        ...
    
    def generate_structured(
        self,
        prompt: str,
        response_schema: dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Generate structured output (JSON) based on schema.
        
        Args:
            prompt: User prompt/question.
            response_schema: Expected JSON schema for response.
            system_prompt: Optional system instructions.
            
        Returns:
            Parsed JSON response matching schema.
        """
        ...


@runtime_checkable
class EmbeddingServiceProtocol(Protocol):
    """
    Protocol for embedding service dependency.
    
    Implementations must provide methods for computing embeddings
    and semantic similarity.
    """
    
    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for text.
        
        Args:
            text: Text to embed.
            
        Returns:
            Embedding vector as list of floats.
        """
        ...
    
    def compute_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float]
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector.
            embedding2: Second embedding vector.
            
        Returns:
            Similarity score between 0.0 and 1.0.
        """
        ...


# =============================================================================
# Keyword Patterns
# =============================================================================


# Aggregation keywords (Requirement 6.2)
AGGREGATION_KEYWORDS: set[str] = {
    "sum", "total", "average", "avg", "count", "min", "max",
    "median", "mean", "aggregate", "calculate", "how many",
    "how much", "number of", "amount of"
}

# Aggregation function patterns
AGGREGATION_FUNCTION_PATTERNS: list[tuple[str, str]] = [
    (r'\b(sum|total)\b', "SUM"),
    (r'\b(average|avg|mean)\b', "AVERAGE"),
    (r'\b(count|how many|number of)\b', "COUNT"),
    (r'\b(min|minimum|lowest|smallest)\b', "MIN"),
    (r'\b(max|maximum|highest|largest|biggest)\b', "MAX"),
    (r'\b(median)\b', "MEDIAN"),
]

# Lookup keywords (Requirement 6.3)
LOOKUP_KEYWORDS: set[str] = {
    "what is", "find", "show", "get", "value of", "look up",
    "retrieve", "fetch", "display", "list", "give me",
    "tell me", "what are", "which", "where is"
}

# Summarization keywords (Requirement 6.4)
SUMMARIZATION_KEYWORDS: set[str] = {
    "summarize", "describe", "overview", "explain", "tell me about",
    "what does", "analyze", "insight", "summary", "describe",
    "breakdown", "analysis", "report on", "give me an overview"
}

# Comparison keywords (Requirement 6.5)
COMPARISON_KEYWORDS: set[str] = {
    "compare", "difference", "versus", "vs", "change between",
    "growth", "trend", "increase", "decrease", "compared to",
    "differ", "contrast", "relative to", "against", "between"
}

# Filter patterns for extracting filter conditions
FILTER_PATTERNS: list[str] = [
    r'\bfor\s+([^,\.]+)',  # "for Q1", "for Product A"
    r'\bwhere\s+([^,\.]+)',  # "where category = X"
    r'\bwith\s+([^,\.]+)',  # "with status active"
    r'\bin\s+(\d{4}|\w+\s+\d{4})',  # "in 2024", "in January 2024"
    r'\bfrom\s+([^,\.]+)',  # "from last month"
    r'\bof\s+([^,\.]+)',  # "of department X"
    r'\bby\s+([^,\.]+)',  # "by region"
]

# Column name patterns
COLUMN_PATTERNS: list[str] = [
    r'\b(sales|revenue|cost|price|amount|quantity|total|profit)\b',
    r'\b(date|time|year|month|quarter|week|day)\b',
    r'\b(name|id|code|category|type|status|region|department)\b',
    r'\b(customer|product|order|invoice|employee|vendor)\b',
]


# =============================================================================
# LLM Classification Prompt
# =============================================================================


LLM_CLASSIFICATION_SYSTEM_PROMPT = """You are a query classifier for an Excel data analysis system.
Your task is to classify natural language queries into one of four types:

1. AGGREGATION: Queries asking for computed values like sums, averages, counts, min/max.
   Examples: "What is the total sales?", "How many orders in Q1?", "Average price per unit"

2. LOOKUP: Queries asking for specific values, rows, or data points.
   Examples: "What is the price of Product A?", "Show me orders from John", "Find customer ID 123"

3. SUMMARIZATION: Queries asking for overviews, descriptions, or analysis of data.
   Examples: "Summarize the sales data", "Give me an overview of Q1 performance", "Describe the trends"

4. COMPARISON: Queries comparing data across files, sheets, time periods, or categories.
   Examples: "Compare Q1 vs Q2 sales", "How did revenue change from 2023 to 2024?", "Difference between regions"

Respond with a JSON object containing:
- query_type: One of "aggregation", "lookup", "summarization", "comparison"
- confidence: A number between 0 and 1 indicating your confidence
- reasoning: Brief explanation of why you chose this classification
- detected_aggregations: List of aggregation functions if applicable (SUM, AVERAGE, COUNT, MIN, MAX, MEDIAN)
- detected_filters: List of filter conditions found in the query
- detected_columns: List of column names or data fields mentioned"""


LLM_CLASSIFICATION_USER_PROMPT = """Classify the following query:

Query: "{query}"

Respond with valid JSON only."""


# =============================================================================
# QueryClassifier Implementation
# =============================================================================


class QueryClassifier:
    """
    Classifies queries into types: aggregation, lookup, summarization, comparison.
    
    Uses keyword-based pattern matching for clear cases and LLM fallback for
    ambiguous queries. Returns confidence scores and alternative classifications
    when confidence is below threshold.
    
    Implements Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7.
    
    Example:
        >>> config = ClassifierConfig()
        >>> classifier = QueryClassifier(
        ...     llm_service=llm_svc,
        ...     embedding_service=embed_svc,
        ...     config=config
        ... )
        >>> result = classifier.classify("What is the total sales for Q1?")
        >>> print(result.query_type)  # QueryType.AGGREGATION
        >>> print(result.confidence)  # 0.95
    """
    
    def __init__(
        self,
        llm_service: LLMServiceProtocol,
        embedding_service: EmbeddingServiceProtocol,
        config: Optional[ClassifierConfig] = None
    ) -> None:
        """
        Initialize QueryClassifier with injected dependencies.
        
        Args:
            llm_service: Service for LLM-based classification.
            embedding_service: Service for semantic similarity.
            config: Optional configuration (uses defaults if not provided).
            
        Raises:
            ValueError: If any required dependency is None.
        """
        if llm_service is None:
            raise ValueError("llm_service is required")
        if embedding_service is None:
            raise ValueError("embedding_service is required")
        
        self._llm_service = llm_service
        self._embedding_service = embedding_service
        self._config = config or ClassifierConfig()
        
        logger.info(
            f"QueryClassifier initialized with confidence_threshold="
            f"{self._config.confidence_threshold}, use_llm_fallback="
            f"{self._config.use_llm_fallback}"
        )

    def classify(self, query: str) -> QueryClassification:
        """
        Classify the query and extract parameters.
        
        Implements Requirement 6.1: Classify queries into aggregation, lookup,
        summarization, or comparison types.
        
        Args:
            query: Natural language query to classify.
            
        Returns:
            QueryClassification with type, confidence, and extracted parameters.
            If confidence < 0.6, includes top 2 alternative classifications
            (Requirement 6.7).
            
        Raises:
            ClassificationError: If classification fails.
        """
        if not query or not query.strip():
            raise ClassificationError(
                "Query cannot be empty",
                details={"query": query}
            )
        
        query = query.strip()
        logger.info(f"Classifying query: {query[:100]}...")
        
        try:
            # Step 1: Keyword-based classification
            keyword_result = self._classify_by_keywords(query)
            
            # Step 2: Extract parameters
            detected_aggregations = self._extract_aggregations(query)
            detected_filters = self._extract_filters(query)
            detected_columns = self._extract_columns(query)
            
            # Step 3: Check if LLM fallback is needed
            if (
                keyword_result["confidence"] < self._config.confidence_threshold
                and self._config.use_llm_fallback
            ):
                logger.debug(
                    f"Keyword confidence {keyword_result['confidence']:.2f} below "
                    f"threshold {self._config.confidence_threshold}, using LLM"
                )
                llm_result = self._classify_by_llm(query)
                
                # Merge results, preferring LLM for type but keeping extracted params
                if llm_result["confidence"] > keyword_result["confidence"]:
                    keyword_result = llm_result
                    # Update extracted params from LLM if available
                    if llm_result.get("detected_aggregations"):
                        detected_aggregations = llm_result["detected_aggregations"]
                    if llm_result.get("detected_filters"):
                        detected_filters = llm_result["detected_filters"]
                    if llm_result.get("detected_columns"):
                        detected_columns = llm_result["detected_columns"]
            
            # Step 4: Build alternative types if confidence < threshold
            alternative_types: list[tuple[QueryType, float]] = []
            if keyword_result["confidence"] < self._config.alternative_threshold:
                alternative_types = self._get_alternative_types(
                    query=query,
                    primary_type=keyword_result["query_type"],
                    primary_confidence=keyword_result["confidence"]
                )
            
            # Step 5: Create classification result
            classification = QueryClassification(
                query_type=keyword_result["query_type"],
                confidence=keyword_result["confidence"],
                alternative_types=alternative_types,
                detected_aggregations=detected_aggregations,
                detected_filters=detected_filters,
                detected_columns=detected_columns
            )
            
            logger.info(
                f"Classified query as {classification.query_type.value} "
                f"with confidence {classification.confidence:.2f}"
            )
            
            return classification
            
        except ClassificationError:
            raise
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            raise ClassificationError(
                f"Failed to classify query: {str(e)}",
                details={"query": query, "error": str(e)}
            )

    def _classify_by_keywords(self, query: str) -> dict[str, Any]:
        """
        Classify query using keyword matching.
        
        Implements Requirements 6.2, 6.3, 6.4, 6.5: Keyword-based classification
        for aggregation, lookup, summarization, and comparison queries.
        
        Args:
            query: Query text.
            
        Returns:
            Dict with query_type, confidence, and scores.
        """
        query_lower = query.lower()
        
        # Calculate scores for each type
        scores: dict[QueryType, float] = {
            QueryType.AGGREGATION: self._calculate_keyword_score(
                query_lower, AGGREGATION_KEYWORDS
            ),
            QueryType.LOOKUP: self._calculate_keyword_score(
                query_lower, LOOKUP_KEYWORDS
            ),
            QueryType.SUMMARIZATION: self._calculate_keyword_score(
                query_lower, SUMMARIZATION_KEYWORDS
            ),
            QueryType.COMPARISON: self._calculate_keyword_score(
                query_lower, COMPARISON_KEYWORDS
            ),
        }
        
        # Apply boosting for strong indicators
        scores = self._apply_score_boosting(query_lower, scores)
        
        # Find the best match
        best_type = max(scores, key=scores.get)  # type: ignore
        best_score = scores[best_type]
        
        # Normalize confidence based on score distribution
        total_score = sum(scores.values())
        if total_score > 0:
            confidence = best_score / total_score
            # Scale confidence based on absolute score
            confidence = min(1.0, confidence * (1 + best_score))
        else:
            confidence = 0.25  # Equal probability if no keywords match
        
        logger.debug(
            f"Keyword scores: {', '.join(f'{t.value}={s:.2f}' for t, s in scores.items())}"
        )
        
        return {
            "query_type": best_type,
            "confidence": min(1.0, confidence),
            "scores": scores
        }

    def _calculate_keyword_score(
        self,
        query_lower: str,
        keywords: set[str]
    ) -> float:
        """
        Calculate keyword match score for a query.
        
        Args:
            query_lower: Lowercase query text.
            keywords: Set of keywords to match.
            
        Returns:
            Score between 0.0 and 1.0.
        """
        matches = 0
        total_weight = 0
        
        for keyword in keywords:
            # Check for exact phrase match (higher weight)
            if keyword in query_lower:
                # Multi-word phrases get higher weight
                word_count = len(keyword.split())
                weight = 1.0 + (word_count - 1) * 0.5
                matches += weight
                total_weight += weight
            else:
                # Check for individual word matches (lower weight)
                keyword_words = keyword.split()
                for word in keyword_words:
                    if len(word) >= 3 and word in query_lower:
                        matches += 0.3
                        total_weight += 0.3
        
        if total_weight == 0:
            return 0.0
        
        # Normalize by number of keywords checked
        return min(1.0, matches / len(keywords))

    def _apply_score_boosting(
        self,
        query_lower: str,
        scores: dict[QueryType, float]
    ) -> dict[QueryType, float]:
        """
        Apply boosting for strong classification indicators.
        
        Args:
            query_lower: Lowercase query text.
            scores: Current scores by type.
            
        Returns:
            Boosted scores.
        """
        boosted = scores.copy()
        
        # Boost aggregation for explicit function mentions
        for pattern, _ in AGGREGATION_FUNCTION_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                boosted[QueryType.AGGREGATION] = min(
                    1.0, boosted[QueryType.AGGREGATION] + 0.3
                )
                break
        
        # Boost comparison for "vs", "versus", "compared to"
        if re.search(r'\b(vs\.?|versus|compared\s+to)\b', query_lower):
            boosted[QueryType.COMPARISON] = min(
                1.0, boosted[QueryType.COMPARISON] + 0.4
            )
        
        # Boost lookup for question patterns
        if re.search(r'^(what|which|where|who|when)\s+(is|are|was|were)\b', query_lower):
            boosted[QueryType.LOOKUP] = min(
                1.0, boosted[QueryType.LOOKUP] + 0.2
            )
        
        # Boost summarization for "overview", "summary", "describe"
        if re.search(r'\b(overview|summary|describe|summarize)\b', query_lower):
            boosted[QueryType.SUMMARIZATION] = min(
                1.0, boosted[QueryType.SUMMARIZATION] + 0.3
            )
        
        return boosted

    def _classify_by_llm(self, query: str) -> dict[str, Any]:
        """
        Classify query using LLM for ambiguous cases.
        
        Args:
            query: Query text.
            
        Returns:
            Dict with query_type, confidence, and extracted parameters.
        """
        try:
            prompt = LLM_CLASSIFICATION_USER_PROMPT.format(query=query)
            
            response = self._llm_service.generate(
                prompt=prompt,
                system_prompt=LLM_CLASSIFICATION_SYSTEM_PROMPT,
                temperature=self._config.llm_temperature,
                max_tokens=self._config.llm_max_tokens
            )
            
            # Parse JSON response
            result = self._parse_llm_response(response)
            
            logger.debug(f"LLM classification result: {result}")
            
            return result
            
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")
            # Return low confidence result on failure
            return {
                "query_type": QueryType.LOOKUP,  # Default fallback
                "confidence": 0.3,
                "detected_aggregations": [],
                "detected_filters": [],
                "detected_columns": []
            }

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        """
        Parse LLM JSON response into classification result.
        
        Args:
            response: Raw LLM response text.
            
        Returns:
            Parsed classification dict.
        """
        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object directly
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                json_str = json_match.group(0)
            else:
                raise ValueError("No JSON found in LLM response")
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in LLM response: {e}")
        
        # Map query_type string to enum
        type_str = data.get("query_type", "lookup").lower()
        type_mapping = {
            "aggregation": QueryType.AGGREGATION,
            "lookup": QueryType.LOOKUP,
            "summarization": QueryType.SUMMARIZATION,
            "comparison": QueryType.COMPARISON,
        }
        query_type = type_mapping.get(type_str, QueryType.LOOKUP)
        
        # Extract confidence
        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        
        return {
            "query_type": query_type,
            "confidence": confidence,
            "detected_aggregations": data.get("detected_aggregations", []),
            "detected_filters": data.get("detected_filters", []),
            "detected_columns": data.get("detected_columns", [])
        }

    def _get_alternative_types(
        self,
        query: str,
        primary_type: QueryType,
        primary_confidence: float
    ) -> list[tuple[QueryType, float]]:
        """
        Get alternative classification types when confidence is low.
        
        Implements Requirement 6.7: Return top 2 most likely classifications
        when confidence < 0.6.
        
        Args:
            query: Query text.
            primary_type: Primary classification type.
            primary_confidence: Primary classification confidence.
            
        Returns:
            List of (QueryType, confidence) tuples for alternatives.
        """
        query_lower = query.lower()
        
        # Calculate scores for all types
        scores: dict[QueryType, float] = {
            QueryType.AGGREGATION: self._calculate_keyword_score(
                query_lower, AGGREGATION_KEYWORDS
            ),
            QueryType.LOOKUP: self._calculate_keyword_score(
                query_lower, LOOKUP_KEYWORDS
            ),
            QueryType.SUMMARIZATION: self._calculate_keyword_score(
                query_lower, SUMMARIZATION_KEYWORDS
            ),
            QueryType.COMPARISON: self._calculate_keyword_score(
                query_lower, COMPARISON_KEYWORDS
            ),
        }
        
        # Apply boosting
        scores = self._apply_score_boosting(query_lower, scores)
        
        # Sort by score descending, excluding primary type
        alternatives = [
            (qtype, score)
            for qtype, score in sorted(
                scores.items(),
                key=lambda x: x[1],
                reverse=True
            )
            if qtype != primary_type and score > 0
        ]
        
        # Normalize scores to confidence values
        total_score = sum(s for _, s in alternatives) + primary_confidence
        if total_score > 0:
            alternatives = [
                (qtype, min(0.99, score / total_score))
                for qtype, score in alternatives
            ]
        
        # Return top N alternatives
        return alternatives[:self._config.max_alternatives]

    def _extract_aggregations(self, query: str) -> list[str]:
        """
        Extract aggregation functions from query.
        
        Args:
            query: Query text.
            
        Returns:
            List of detected aggregation functions (SUM, AVERAGE, etc.).
        """
        aggregations: list[str] = []
        query_lower = query.lower()
        
        for pattern, function_name in AGGREGATION_FUNCTION_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                if function_name not in aggregations:
                    aggregations.append(function_name)
        
        return aggregations

    def _extract_filters(self, query: str) -> list[str]:
        """
        Extract filter conditions from query.
        
        Args:
            query: Query text.
            
        Returns:
            List of detected filter conditions.
        """
        filters: list[str] = []
        
        for pattern in FILTER_PATTERNS:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                filter_text = match.strip()
                if filter_text and len(filter_text) > 2:
                    # Clean up the filter text
                    filter_text = re.sub(r'\s+', ' ', filter_text)
                    if filter_text not in filters:
                        filters.append(filter_text)
        
        return filters

    def _extract_columns(self, query: str) -> list[str]:
        """
        Extract column/field names from query.
        
        Args:
            query: Query text.
            
        Returns:
            List of detected column names.
        """
        columns: list[str] = []
        query_lower = query.lower()
        
        for pattern in COLUMN_PATTERNS:
            matches = re.findall(pattern, query_lower, re.IGNORECASE)
            for match in matches:
                if match not in columns:
                    columns.append(match)
        
        return columns
