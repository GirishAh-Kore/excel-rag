"""
Sheet Selector Module for Smart Excel Query Pipeline.

This module implements intelligent sheet selection based on name similarity,
header/column matching, data type alignment, and content similarity.
It provides explainability for ranking decisions and handles threshold-based
selection behavior including multi-sheet combination strategies.

Key Components:
- SheetSelector: Main class for ranking and selecting sheets
- SheetMetadataProtocol: Protocol for sheet metadata access
- EmbeddingServiceProtocol: Protocol for embedding service dependency
- SheetSelectionResult: Result of sheet selection with candidates and explanations
- SheetRankingExplanation: Detailed explanation of ranking decisions
- CombinationStrategy: Strategy for combining multiple sheets

Supports Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6.
"""

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

from src.exceptions import SelectionError
from src.models.query_pipeline import SheetCandidate

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class SheetSelectorConfig:
    """
    Configuration for SheetSelector.
    
    Attributes:
        name_weight: Weight for sheet name similarity score (default 0.3).
        header_weight: Weight for header/column matching score (default 0.4).
        data_type_weight: Weight for data type alignment score (default 0.2).
        content_weight: Weight for content similarity score (default 0.1).
        auto_select_threshold: Threshold for automatic selection (default 0.7).
        clarify_threshold: Threshold below which clarification is needed (default 0.5).
        max_candidates: Maximum number of candidates to return (default 5).
        fuzzy_match_threshold: Threshold for fuzzy name matching (default 0.6).
    """
    name_weight: float = 0.3
    header_weight: float = 0.4
    data_type_weight: float = 0.2
    content_weight: float = 0.1
    auto_select_threshold: float = 0.7
    clarify_threshold: float = 0.5
    max_candidates: int = 5
    fuzzy_match_threshold: float = 0.6
    
    def __post_init__(self) -> None:
        """Validate configuration values."""
        total_weight = (
            self.name_weight + self.header_weight + 
            self.data_type_weight + self.content_weight
        )
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(
                f"Weights must sum to 1.0, got {total_weight} "
                f"(name={self.name_weight}, header={self.header_weight}, "
                f"data_type={self.data_type_weight}, content={self.content_weight})"
            )
        
        if not 0.0 <= self.auto_select_threshold <= 1.0:
            raise ValueError(f"auto_select_threshold must be 0-1, got {self.auto_select_threshold}")
        
        if not 0.0 <= self.clarify_threshold <= 1.0:
            raise ValueError(f"clarify_threshold must be 0-1, got {self.clarify_threshold}")
        
        if self.clarify_threshold >= self.auto_select_threshold:
            raise ValueError(
                f"clarify_threshold ({self.clarify_threshold}) must be less than "
                f"auto_select_threshold ({self.auto_select_threshold})"
            )


# =============================================================================
# Protocols (Dependency Injection Interfaces)
# =============================================================================


@runtime_checkable
class EmbeddingServiceProtocol(Protocol):
    """
    Protocol for embedding service dependency.
    
    Implementations must provide methods for computing semantic similarity
    between query text and sheet content.
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
    
    def compute_similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector.
            embedding2: Second embedding vector.
            
        Returns:
            Similarity score between 0.0 and 1.0.
        """
        ...


@runtime_checkable
class SheetMetadataProtocol(Protocol):
    """
    Protocol for sheet metadata access.
    
    Implementations must provide methods for retrieving sheet metadata
    including headers, data types, and content samples.
    """
    
    def get_sheets_for_file(self, file_id: str) -> list[dict[str, Any]]:
        """
        Get metadata for all sheets in a file.
        
        Args:
            file_id: File identifier.
            
        Returns:
            List of sheet metadata dictionaries with keys:
            - sheet_name: Name of the sheet
            - headers: List of column headers
            - data_types: Dict mapping column names to detected types
            - row_count: Number of data rows
            - column_count: Number of columns
            - sample_content: Sample of sheet content (optional)
            - embedding: Pre-computed embedding vector (optional)
        """
        ...
    
    def get_sheet_embedding(self, file_id: str, sheet_name: str) -> Optional[list[float]]:
        """
        Get pre-computed embedding for a sheet.
        
        Args:
            file_id: File identifier.
            sheet_name: Sheet name.
            
        Returns:
            Embedding vector or None if not available.
        """
        ...


# =============================================================================
# Enums and Result Types
# =============================================================================


class SelectionAction(str, Enum):
    """Action to take based on sheet selection results."""
    AUTO_SELECT = "auto_select"  # Confidence > 0.7
    MULTI_SHEET = "multi_sheet"  # Multiple sheets > 0.7
    CLARIFY = "clarify"  # Confidence < 0.5


class CombinationStrategy(str, Enum):
    """Strategy for combining multiple sheets."""
    UNION = "union"  # Combine rows from sheets with same structure
    JOIN = "join"  # Join sheets on common columns
    SEPARATE = "separate"  # Keep sheets separate, query each


@dataclass
class ScoreBreakdown:
    """
    Breakdown of scoring components for a sheet.
    
    Attributes:
        name_score: Raw sheet name similarity score.
        header_score: Raw header/column matching score.
        data_type_score: Raw data type alignment score.
        content_score: Raw content similarity score.
        weighted_name: Weighted name score.
        weighted_header: Weighted header score.
        weighted_data_type: Weighted data type score.
        weighted_content: Weighted content score.
    """
    name_score: float
    header_score: float
    data_type_score: float
    content_score: float
    weighted_name: float = 0.0
    weighted_header: float = 0.0
    weighted_data_type: float = 0.0
    weighted_content: float = 0.0


@dataclass
class SheetRankingExplanation:
    """
    Detailed explanation of why a sheet was ranked as it was.
    
    Supports Requirement 5.6: Provide explainability for sheet ranking decisions.
    
    Attributes:
        sheet_name: Name of the sheet.
        combined_score: Final combined score.
        score_breakdown: Detailed score breakdown.
        ranking_reasons: Human-readable reasons for the ranking.
        matched_headers: Headers that matched the query.
        matched_data_types: Data types that aligned with query intent.
        name_match_type: Type of name match (exact, fuzzy, none).
    """
    sheet_name: str
    combined_score: float
    score_breakdown: ScoreBreakdown
    ranking_reasons: list[str] = field(default_factory=list)
    matched_headers: list[str] = field(default_factory=list)
    matched_data_types: list[str] = field(default_factory=list)
    name_match_type: str = "none"


@dataclass
class SheetSelectionResult:
    """
    Result of sheet selection process.
    
    Attributes:
        action: Action to take (auto_select, multi_sheet, clarify).
        selected_sheets: Auto-selected sheet(s) if action is AUTO_SELECT or MULTI_SHEET.
        combination_strategy: Strategy for combining multiple sheets.
        candidates: All candidates for user selection.
        explanations: Detailed explanations for all ranked sheets.
        message: Human-readable message about the selection.
        top_confidence: Confidence score of the top-ranked sheet.
    """
    action: SelectionAction
    selected_sheets: list[SheetCandidate] = field(default_factory=list)
    combination_strategy: Optional[CombinationStrategy] = None
    candidates: list[SheetCandidate] = field(default_factory=list)
    explanations: dict[str, SheetRankingExplanation] = field(default_factory=dict)
    message: str = ""
    top_confidence: float = 0.0


# =============================================================================
# Data Type Detection Patterns
# =============================================================================


# Patterns for detecting query intent related to data types
DATA_TYPE_PATTERNS = {
    "numeric": [
        r'\b(sum|total|average|avg|count|min|max|median|mean)\b',
        r'\b(amount|price|cost|revenue|sales|quantity|number)\b',
        r'\b(percentage|percent|ratio|rate)\b',
    ],
    "date": [
        r'\b(date|time|when|year|month|day|quarter)\b',
        r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',
        r'\b(q[1-4]|fy\d{2,4})\b',
    ],
    "text": [
        r'\b(name|description|title|label|category|type)\b',
        r'\b(who|what|which)\b',
    ],
}


# =============================================================================
# SheetSelector Implementation
# =============================================================================


class SheetSelector:
    """
    Ranks and selects sheets based on name similarity, header matching,
    data type alignment, and content similarity.
    
    Implements the smart sheet selection algorithm with:
    - Weighted scoring: name (30%), header (40%), data_type (20%), content (10%)
    - Threshold behavior: auto-select >0.7, multi-sheet combination, clarify <0.5
    - Combination strategy determination for multi-sheet queries
    - Explainability for ranking decisions
    
    Supports Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6.
    
    Example:
        >>> config = SheetSelectorConfig()
        >>> selector = SheetSelector(
        ...     embedding_service=embedding_svc,
        ...     sheet_metadata=sheet_meta,
        ...     config=config
        ... )
        >>> result = selector.rank_sheets("file_123", "What were sales in Q1?")
        >>> if result.action == SelectionAction.AUTO_SELECT:
        ...     selected = result.selected_sheets[0]
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingServiceProtocol,
        sheet_metadata: SheetMetadataProtocol,
        config: Optional[SheetSelectorConfig] = None
    ) -> None:
        """
        Initialize SheetSelector with injected dependencies.
        
        Args:
            embedding_service: Service for computing semantic similarity.
            sheet_metadata: Provider for sheet metadata.
            config: Optional configuration (uses defaults if not provided).
            
        Raises:
            ValueError: If any required dependency is None.
        """
        if embedding_service is None:
            raise ValueError("embedding_service is required")
        if sheet_metadata is None:
            raise ValueError("sheet_metadata is required")
        
        self._embedding_service = embedding_service
        self._sheet_metadata = sheet_metadata
        self._config = config or SheetSelectorConfig()
        
        logger.info(
            f"SheetSelector initialized with weights: "
            f"name={self._config.name_weight}, "
            f"header={self._config.header_weight}, "
            f"data_type={self._config.data_type_weight}, "
            f"content={self._config.content_weight}"
        )

    def rank_sheets(
        self,
        file_id: str,
        query: str
    ) -> SheetSelectionResult:
        """
        Rank all sheets in a file by relevance to the query.
        
        Implements Requirement 5.1: Rank sheets using name similarity (30%),
        header/column matching (40%), data type alignment (20%), and
        content similarity (10%).
        
        Args:
            file_id: ID of the file to select sheets from.
            query: Natural language query.
            
        Returns:
            SheetSelectionResult with ranked candidates and selection action.
            
        Raises:
            SelectionError: If no sheets are available or ranking fails.
        """
        logger.info(f"Ranking sheets for file {file_id}, query: {query[:100]}...")
        
        # Get all sheets for the file
        sheets = self._sheet_metadata.get_sheets_for_file(file_id)
        
        if not sheets:
            logger.warning(f"No sheets available for file {file_id}")
            raise SelectionError(
                f"No sheets available for file {file_id}.",
                details={"file_id": file_id, "query": query}
            )
        
        # Extract sheet name mentions from query (Requirement 5.5)
        mentioned_sheets = self._extract_sheet_mentions(query, sheets)
        logger.debug(f"Mentioned sheets in query: {mentioned_sheets}")
        
        # Detect expected data types from query
        expected_types = self._detect_expected_data_types(query)
        logger.debug(f"Expected data types: {expected_types}")
        
        # Compute query embedding
        query_embedding = self._embedding_service.embed_text(query)
        
        # Score each sheet
        candidates: list[SheetCandidate] = []
        explanations: dict[str, SheetRankingExplanation] = {}
        
        for sheet_info in sheets:
            sheet_name = sheet_info.get("sheet_name", "")
            
            try:
                candidate, explanation = self._score_sheet(
                    file_id=file_id,
                    sheet_info=sheet_info,
                    query=query,
                    query_embedding=query_embedding,
                    mentioned_sheets=mentioned_sheets,
                    expected_types=expected_types
                )
                candidates.append(candidate)
                explanations[sheet_name] = explanation
                
            except Exception as e:
                logger.warning(f"Error scoring sheet {sheet_name}: {e}")
                # Create low-score candidate
                candidate = SheetCandidate(
                    sheet_name=sheet_name,
                    name_score=0.0,
                    header_score=0.0,
                    data_type_score=0.0,
                    content_score=0.0,
                    combined_score=0.0
                )
                candidates.append(candidate)
        
        # Sort by combined score descending
        candidates.sort(key=lambda c: c.combined_score, reverse=True)
        
        # Determine selection action based on thresholds
        return self._determine_selection_action(
            candidates=candidates,
            explanations=explanations,
            query=query
        )

    def _score_sheet(
        self,
        file_id: str,
        sheet_info: dict[str, Any],
        query: str,
        query_embedding: list[float],
        mentioned_sheets: set[str],
        expected_types: set[str]
    ) -> tuple[SheetCandidate, SheetRankingExplanation]:
        """
        Score a single sheet against the query.
        
        Args:
            file_id: File identifier.
            sheet_info: Sheet metadata dictionary.
            query: Original query text.
            query_embedding: Pre-computed query embedding.
            mentioned_sheets: Sheet names mentioned in query.
            expected_types: Expected data types from query.
            
        Returns:
            Tuple of (SheetCandidate, SheetRankingExplanation).
        """
        sheet_name = sheet_info.get("sheet_name", "")
        headers = sheet_info.get("headers", [])
        data_types = sheet_info.get("data_types", {})
        
        ranking_reasons: list[str] = []
        matched_headers: list[str] = []
        matched_data_types: list[str] = []
        name_match_type = "none"
        
        # 1. Compute name similarity score (Requirement 5.1 - 30% weight)
        name_score, name_match_type = self._compute_name_score(
            sheet_name=sheet_name,
            query=query,
            mentioned_sheets=mentioned_sheets
        )
        if name_score > 0.8:
            ranking_reasons.append(f"Strong name match ({name_match_type}): {name_score:.2f}")
        elif name_score > 0.5:
            ranking_reasons.append(f"Partial name match ({name_match_type}): {name_score:.2f}")
        
        # 2. Compute header/column matching score (Requirement 5.1 - 40% weight)
        header_score, header_matches = self._compute_header_score(
            headers=headers,
            query=query
        )
        matched_headers.extend(header_matches)
        if header_matches:
            ranking_reasons.append(f"Matching columns: {', '.join(header_matches[:3])}")
        
        # 3. Compute data type alignment score (Requirement 5.1 - 20% weight)
        data_type_score, type_matches = self._compute_data_type_score(
            data_types=data_types,
            expected_types=expected_types
        )
        matched_data_types.extend(type_matches)
        if type_matches:
            ranking_reasons.append(f"Data type alignment: {', '.join(type_matches)}")
        
        # 4. Compute content similarity score (Requirement 5.1 - 10% weight)
        content_score = self._compute_content_score(
            file_id=file_id,
            sheet_info=sheet_info,
            query_embedding=query_embedding
        )
        if content_score > 0.7:
            ranking_reasons.append(f"High content similarity ({content_score:.2f})")
        
        # 5. Compute weighted combined score
        weighted_name = name_score * self._config.name_weight
        weighted_header = header_score * self._config.header_weight
        weighted_data_type = data_type_score * self._config.data_type_weight
        weighted_content = content_score * self._config.content_weight
        
        combined_score = weighted_name + weighted_header + weighted_data_type + weighted_content
        
        # Cap at 1.0
        combined_score = min(1.0, combined_score)
        
        # Create score breakdown
        score_breakdown = ScoreBreakdown(
            name_score=name_score,
            header_score=header_score,
            data_type_score=data_type_score,
            content_score=content_score,
            weighted_name=weighted_name,
            weighted_header=weighted_header,
            weighted_data_type=weighted_data_type,
            weighted_content=weighted_content
        )
        
        # Create candidate
        candidate = SheetCandidate(
            sheet_name=sheet_name,
            name_score=name_score,
            header_score=header_score,
            data_type_score=data_type_score,
            content_score=content_score,
            combined_score=combined_score
        )
        
        # Create explanation
        explanation = SheetRankingExplanation(
            sheet_name=sheet_name,
            combined_score=combined_score,
            score_breakdown=score_breakdown,
            ranking_reasons=ranking_reasons,
            matched_headers=matched_headers,
            matched_data_types=matched_data_types,
            name_match_type=name_match_type
        )
        
        logger.debug(
            f"Scored sheet '{sheet_name}': combined={combined_score:.3f} "
            f"(name={name_score:.3f}, header={header_score:.3f}, "
            f"data_type={data_type_score:.3f}, content={content_score:.3f})"
        )
        
        return candidate, explanation

    def _compute_name_score(
        self,
        sheet_name: str,
        query: str,
        mentioned_sheets: set[str]
    ) -> tuple[float, str]:
        """
        Compute sheet name similarity score.
        
        Implements Requirement 5.5: Prioritize exact and fuzzy name matches.
        
        Args:
            sheet_name: Name of the sheet.
            query: Query text.
            mentioned_sheets: Sheet names mentioned in query.
            
        Returns:
            Tuple of (score, match_type).
        """
        sheet_name_lower = sheet_name.lower()
        query_lower = query.lower()
        
        # Check for exact match in mentioned sheets
        if sheet_name_lower in mentioned_sheets:
            return 1.0, "exact"
        
        # Check for exact substring match in query
        if sheet_name_lower in query_lower:
            return 0.95, "exact_substring"
        
        # Check for fuzzy match with mentioned sheets
        for mentioned in mentioned_sheets:
            similarity = SequenceMatcher(None, sheet_name_lower, mentioned).ratio()
            if similarity >= self._config.fuzzy_match_threshold:
                return similarity, "fuzzy"
        
        # Check for word overlap between sheet name and query
        sheet_words = set(re.split(r'[_\-\s]+', sheet_name_lower))
        query_words = set(query_lower.split())
        
        overlap = sheet_words & query_words
        if overlap:
            overlap_score = len(overlap) / max(len(sheet_words), 1)
            return min(0.7, overlap_score), "word_overlap"
        
        # Check for partial fuzzy match with query words
        best_fuzzy = 0.0
        for query_word in query_words:
            if len(query_word) >= 3:  # Skip short words
                similarity = SequenceMatcher(None, sheet_name_lower, query_word).ratio()
                best_fuzzy = max(best_fuzzy, similarity)
        
        if best_fuzzy >= self._config.fuzzy_match_threshold:
            return best_fuzzy * 0.6, "partial_fuzzy"
        
        return 0.0, "none"

    def _compute_header_score(
        self,
        headers: list[str],
        query: str
    ) -> tuple[float, list[str]]:
        """
        Compute header/column matching score.
        
        Args:
            headers: List of column headers.
            query: Query text.
            
        Returns:
            Tuple of (score, matched_headers).
        """
        if not headers:
            return 0.0, []
        
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        matched_headers: list[str] = []
        
        for header in headers:
            header_lower = header.lower()
            header_words = set(re.split(r'[_\-\s]+', header_lower))
            
            # Check for exact match
            if header_lower in query_lower:
                matched_headers.append(header)
                continue
            
            # Check for word overlap
            if header_words & query_words:
                matched_headers.append(header)
                continue
            
            # Check for fuzzy match
            for query_word in query_words:
                if len(query_word) >= 3:
                    similarity = SequenceMatcher(None, header_lower, query_word).ratio()
                    if similarity >= self._config.fuzzy_match_threshold:
                        matched_headers.append(header)
                        break
        
        if not matched_headers:
            return 0.0, []
        
        # Score based on proportion of matched headers (capped at 1.0)
        score = min(1.0, len(matched_headers) / min(3, len(headers)))
        
        return score, matched_headers

    def _compute_data_type_score(
        self,
        data_types: dict[str, str],
        expected_types: set[str]
    ) -> tuple[float, list[str]]:
        """
        Compute data type alignment score.
        
        Args:
            data_types: Dict mapping column names to detected types.
            expected_types: Expected data types from query analysis.
            
        Returns:
            Tuple of (score, matched_types).
        """
        if not data_types or not expected_types:
            return 0.5, []  # Neutral score when no type info available
        
        matched_types: list[str] = []
        sheet_types = set(data_types.values())
        
        # Map common type names to categories
        type_mapping = {
            "int": "numeric",
            "integer": "numeric",
            "float": "numeric",
            "number": "numeric",
            "decimal": "numeric",
            "currency": "numeric",
            "percentage": "numeric",
            "date": "date",
            "datetime": "date",
            "time": "date",
            "timestamp": "date",
            "str": "text",
            "string": "text",
            "text": "text",
            "varchar": "text",
        }
        
        # Normalize sheet types
        normalized_sheet_types: set[str] = set()
        for t in sheet_types:
            t_lower = t.lower()
            normalized = type_mapping.get(t_lower, t_lower)
            normalized_sheet_types.add(normalized)
        
        # Check for matches
        for expected in expected_types:
            if expected in normalized_sheet_types:
                matched_types.append(expected)
        
        if not matched_types:
            return 0.3, []  # Low score when no type alignment
        
        # Score based on proportion of expected types found
        score = len(matched_types) / len(expected_types)
        
        return score, matched_types

    def _compute_content_score(
        self,
        file_id: str,
        sheet_info: dict[str, Any],
        query_embedding: list[float]
    ) -> float:
        """
        Compute content similarity score using embeddings.
        
        Args:
            file_id: File identifier.
            sheet_info: Sheet metadata with optional embedding.
            query_embedding: Query embedding vector.
            
        Returns:
            Content similarity score (0.0 to 1.0).
        """
        sheet_name = sheet_info.get("sheet_name", "")
        
        # Try to get pre-computed sheet embedding
        sheet_embedding = self._sheet_metadata.get_sheet_embedding(file_id, sheet_name)
        
        if sheet_embedding is None:
            # Fall back to embedding sheet metadata
            headers = sheet_info.get("headers", [])
            sample_content = sheet_info.get("sample_content", "")
            
            sheet_text = f"{sheet_name} {' '.join(headers)} {sample_content}"
            sheet_embedding = self._embedding_service.embed_text(sheet_text)
        
        # Compute cosine similarity
        return self._embedding_service.compute_similarity(query_embedding, sheet_embedding)

    def _extract_sheet_mentions(
        self,
        query: str,
        sheets: list[dict[str, Any]]
    ) -> set[str]:
        """
        Extract sheet names mentioned in the query.
        
        Implements Requirement 5.5: Prioritize exact and fuzzy name matches.
        
        Args:
            query: Query text.
            sheets: List of sheet metadata.
            
        Returns:
            Set of mentioned sheet names (lowercase).
        """
        mentioned: set[str] = set()
        query_lower = query.lower()
        
        for sheet_info in sheets:
            sheet_name = sheet_info.get("sheet_name", "")
            sheet_name_lower = sheet_name.lower()
            
            # Check for exact match
            if sheet_name_lower in query_lower:
                mentioned.add(sheet_name_lower)
                continue
            
            # Check for quoted sheet name
            quoted_patterns = [
                f'"{sheet_name}"',
                f"'{sheet_name}'",
                f'sheet "{sheet_name}"',
                f"sheet '{sheet_name}'",
            ]
            for pattern in quoted_patterns:
                if pattern.lower() in query_lower:
                    mentioned.add(sheet_name_lower)
                    break
        
        return mentioned

    def _detect_expected_data_types(self, query: str) -> set[str]:
        """
        Detect expected data types from query text.
        
        Args:
            query: Query text.
            
        Returns:
            Set of expected data type categories.
        """
        expected: set[str] = set()
        query_lower = query.lower()
        
        for data_type, patterns in DATA_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    expected.add(data_type)
                    break
        
        return expected

    def _determine_selection_action(
        self,
        candidates: list[SheetCandidate],
        explanations: dict[str, SheetRankingExplanation],
        query: str
    ) -> SheetSelectionResult:
        """
        Determine selection action based on confidence thresholds.
        
        Implements Requirements 5.2, 5.3, 5.4:
        - 5.2: Auto-select when top sheet confidence > 0.7
        - 5.3: Multi-sheet combination when multiple sheets > 0.7
        - 5.4: Request clarification when confidence < 0.5
        
        Args:
            candidates: Sorted list of sheet candidates.
            explanations: Explanations for each sheet.
            query: Original query.
            
        Returns:
            SheetSelectionResult with appropriate action.
        """
        if not candidates:
            return SheetSelectionResult(
                action=SelectionAction.CLARIFY,
                message="No sheets available for selection.",
                top_confidence=0.0
            )
        
        top_candidate = candidates[0]
        top_confidence = top_candidate.combined_score
        
        # Find all sheets above auto-select threshold
        high_confidence_sheets = [
            c for c in candidates 
            if c.combined_score > self._config.auto_select_threshold
        ]
        
        # Requirement 5.3: Multiple sheets above threshold
        if len(high_confidence_sheets) > 1:
            combination_strategy = self._determine_combination_strategy(
                sheets=high_confidence_sheets,
                query=query
            )
            
            logger.info(
                f"Multiple sheets above threshold ({len(high_confidence_sheets)}), "
                f"combination strategy: {combination_strategy.value}"
            )
            
            return SheetSelectionResult(
                action=SelectionAction.MULTI_SHEET,
                selected_sheets=high_confidence_sheets,
                combination_strategy=combination_strategy,
                candidates=candidates,
                explanations=explanations,
                message=f"Multiple sheets match your query. "
                        f"Using {combination_strategy.value} strategy to combine: "
                        f"{', '.join(s.sheet_name for s in high_confidence_sheets)}.",
                top_confidence=top_confidence
            )
        
        # Requirement 5.2: Auto-select when confidence > 0.7
        if top_confidence > self._config.auto_select_threshold:
            logger.info(
                f"Auto-selecting sheet '{top_candidate.sheet_name}' "
                f"with confidence {top_confidence:.3f}"
            )
            return SheetSelectionResult(
                action=SelectionAction.AUTO_SELECT,
                selected_sheets=[top_candidate],
                candidates=candidates,
                explanations=explanations,
                message=f"Automatically selected '{top_candidate.sheet_name}' "
                        f"with high confidence ({top_confidence:.2f}).",
                top_confidence=top_confidence
            )
        
        # Requirement 5.4: Request clarification when confidence < 0.5
        if top_confidence < self._config.clarify_threshold:
            logger.info(
                f"Low confidence ({top_confidence:.3f}), requesting clarification"
            )
            
            # Build list of available sheets for clarification message
            sheet_list = ", ".join(c.sheet_name for c in candidates[:self._config.max_candidates])
            
            return SheetSelectionResult(
                action=SelectionAction.CLARIFY,
                candidates=candidates[:self._config.max_candidates],
                explanations=explanations,
                message=f"No sheets match your query with high confidence "
                        f"(best match: {top_confidence:.2f}). "
                        f"Available sheets: {sheet_list}. "
                        f"Please specify which sheet you want to query.",
                top_confidence=top_confidence
            )
        
        # Medium confidence: present candidates but auto-select top one
        logger.info(
            f"Medium confidence ({top_confidence:.3f}), auto-selecting top candidate"
        )
        return SheetSelectionResult(
            action=SelectionAction.AUTO_SELECT,
            selected_sheets=[top_candidate],
            candidates=candidates[:self._config.max_candidates],
            explanations=explanations,
            message=f"Selected '{top_candidate.sheet_name}' "
                    f"with moderate confidence ({top_confidence:.2f}).",
            top_confidence=top_confidence
        )

    def _determine_combination_strategy(
        self,
        sheets: list[SheetCandidate],
        query: str
    ) -> CombinationStrategy:
        """
        Determine how to combine multiple sheets based on query intent.
        
        Implements Requirement 5.3: Determine if data should be combined (union),
        joined, or kept separate based on query intent.
        
        Args:
            sheets: List of high-confidence sheet candidates.
            query: Original query.
            
        Returns:
            CombinationStrategy for handling multiple sheets.
        """
        query_lower = query.lower()
        
        # Check for comparison keywords -> keep separate
        comparison_keywords = [
            "compare", "versus", "vs", "difference", "between",
            "against", "relative to"
        ]
        for keyword in comparison_keywords:
            if keyword in query_lower:
                return CombinationStrategy.SEPARATE
        
        # Check for join keywords -> join
        join_keywords = [
            "join", "combine with", "merge", "link", "relate",
            "match", "lookup from"
        ]
        for keyword in join_keywords:
            if keyword in query_lower:
                return CombinationStrategy.JOIN
        
        # Check for aggregation across sheets -> union
        aggregation_keywords = [
            "total", "sum", "all", "overall", "combined",
            "aggregate", "across"
        ]
        for keyword in aggregation_keywords:
            if keyword in query_lower:
                return CombinationStrategy.UNION
        
        # Default to separate for safety
        return CombinationStrategy.SEPARATE

    def get_explanation(
        self,
        result: SheetSelectionResult,
        sheet_name: str
    ) -> Optional[SheetRankingExplanation]:
        """
        Get detailed explanation for a specific sheet's ranking.
        
        Implements Requirement 5.6: Provide explainability for ranking decisions.
        
        Args:
            result: Sheet selection result.
            sheet_name: Sheet to get explanation for.
            
        Returns:
            SheetRankingExplanation or None if not found.
        """
        return result.explanations.get(sheet_name)

    def format_explanation_text(
        self,
        explanation: SheetRankingExplanation
    ) -> str:
        """
        Format explanation as human-readable text.
        
        Args:
            explanation: Sheet ranking explanation.
            
        Returns:
            Formatted explanation string.
        """
        lines = [
            f"Sheet: {explanation.sheet_name}",
            f"Combined Score: {explanation.combined_score:.3f}",
            f"Name Match Type: {explanation.name_match_type}",
            "",
            "Score Breakdown:",
            f"  - Name: {explanation.score_breakdown.name_score:.3f} "
            f"(weighted: {explanation.score_breakdown.weighted_name:.3f})",
            f"  - Header: {explanation.score_breakdown.header_score:.3f} "
            f"(weighted: {explanation.score_breakdown.weighted_header:.3f})",
            f"  - Data Type: {explanation.score_breakdown.data_type_score:.3f} "
            f"(weighted: {explanation.score_breakdown.weighted_data_type:.3f})",
            f"  - Content: {explanation.score_breakdown.content_score:.3f} "
            f"(weighted: {explanation.score_breakdown.weighted_content:.3f})",
        ]
        
        if explanation.ranking_reasons:
            lines.append("")
            lines.append("Ranking Reasons:")
            for reason in explanation.ranking_reasons:
                lines.append(f"  • {reason}")
        
        if explanation.matched_headers:
            lines.append("")
            lines.append(f"Matched Headers: {', '.join(explanation.matched_headers)}")
        
        if explanation.matched_data_types:
            lines.append(f"Matched Data Types: {', '.join(explanation.matched_data_types)}")
        
        return "\n".join(lines)
