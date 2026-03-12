"""
File Selector Module for Smart Excel Query Pipeline.

This module implements intelligent file selection based on semantic similarity,
metadata matching, and user preference history. It provides explainability
for ranking decisions and handles threshold-based selection behavior.

Key Components:
- FileSelector: Main class for ranking and selecting files
- EmbeddingServiceProtocol: Protocol for embedding service dependency
- PreferenceStoreProtocol: Protocol for preference storage dependency
- FileMetadataProtocol: Protocol for file metadata access
- FileSelectionResult: Result of file selection with candidates and explanations
- FileRankingExplanation: Detailed explanation of ranking decisions

Supports Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

from src.exceptions import SelectionError
from src.models.query_pipeline import FileCandidate

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class FileSelectorConfig:
    """
    Configuration for FileSelector.
    
    Attributes:
        semantic_weight: Weight for semantic similarity score (default 0.5).
        metadata_weight: Weight for metadata matching score (default 0.3).
        preference_weight: Weight for user preference score (default 0.2).
        auto_select_threshold: Threshold for automatic selection (default 0.9).
        clarify_threshold: Threshold below which clarification is needed (default 0.5).
        max_candidates: Maximum number of candidates to return (default 3).
        temporal_boost_factor: Boost factor for temporal matches (default 0.2).
    """
    semantic_weight: float = 0.5
    metadata_weight: float = 0.3
    preference_weight: float = 0.2
    auto_select_threshold: float = 0.9
    clarify_threshold: float = 0.5
    max_candidates: int = 3
    temporal_boost_factor: float = 0.2
    
    def __post_init__(self) -> None:
        """Validate configuration values."""
        total_weight = self.semantic_weight + self.metadata_weight + self.preference_weight
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(
                f"Weights must sum to 1.0, got {total_weight} "
                f"(semantic={self.semantic_weight}, metadata={self.metadata_weight}, "
                f"preference={self.preference_weight})"
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
    between query text and file content/metadata.
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
class PreferenceStoreProtocol(Protocol):
    """
    Protocol for preference storage dependency.
    
    Implementations must provide methods for recording and retrieving
    user file selection preferences.
    """
    
    def record_selection(
        self,
        query: str,
        file_id: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Record a user's file selection.
        
        Args:
            query: Query that led to selection.
            file_id: ID of selected file.
            user_id: Optional user identifier.
            
        Returns:
            True if recording succeeded.
        """
        ...
    
    def get_preference_score(
        self,
        query: str,
        file_id: str,
        user_id: Optional[str] = None
    ) -> float:
        """
        Get preference score for a file based on historical selections.
        
        Args:
            query: Current query.
            file_id: File to get preference for.
            user_id: Optional user identifier.
            
        Returns:
            Preference score between 0.0 and 1.0.
        """
        ...


@runtime_checkable
class FileMetadataProtocol(Protocol):
    """
    Protocol for file metadata access.
    
    Implementations must provide methods for retrieving file metadata
    and embeddings for indexed files.
    """
    
    def get_all_indexed_files(self) -> list[dict[str, Any]]:
        """
        Get metadata for all indexed files.
        
        Returns:
            List of file metadata dictionaries with keys:
            - file_id: Unique file identifier
            - file_name: Name of the file
            - file_path: Full path to the file
            - modified_time: Last modification timestamp
            - embedding: Pre-computed embedding vector (optional)
            - columns: List of column names (optional)
            - sheet_names: List of sheet names (optional)
        """
        ...
    
    def get_file_embedding(self, file_id: str) -> Optional[list[float]]:
        """
        Get pre-computed embedding for a file.
        
        Args:
            file_id: File identifier.
            
        Returns:
            Embedding vector or None if not available.
        """
        ...


# =============================================================================
# Result Types
# =============================================================================


class SelectionAction(str, Enum):
    """Action to take based on file selection results."""
    AUTO_SELECT = "auto_select"  # Confidence > 0.9
    CLARIFY = "clarify"  # Confidence 0.5-0.9
    LOW_CONFIDENCE = "low_confidence"  # Confidence < 0.5


@dataclass
class ScoreBreakdown:
    """
    Breakdown of scoring components for a file.
    
    Attributes:
        semantic_score: Raw semantic similarity score.
        metadata_score: Raw metadata matching score.
        preference_score: Raw user preference score.
        temporal_boost: Boost applied for temporal matches.
        weighted_semantic: Weighted semantic score.
        weighted_metadata: Weighted metadata score.
        weighted_preference: Weighted preference score.
    """
    semantic_score: float
    metadata_score: float
    preference_score: float
    temporal_boost: float = 0.0
    weighted_semantic: float = 0.0
    weighted_metadata: float = 0.0
    weighted_preference: float = 0.0


@dataclass
class FileRankingExplanation:
    """
    Detailed explanation of why a file was ranked as it was.
    
    Supports Requirement 4.7: Provide explainability for file ranking decisions.
    
    Attributes:
        file_id: File identifier.
        file_name: Name of the file.
        combined_score: Final combined score.
        score_breakdown: Detailed score breakdown.
        ranking_reasons: Human-readable reasons for the ranking.
        matched_temporal_refs: Temporal references that matched.
        matched_columns: Columns that matched the query.
        rejection_reason: Reason if file was rejected (Requirement 4.8).
    """
    file_id: str
    file_name: str
    combined_score: float
    score_breakdown: ScoreBreakdown
    ranking_reasons: list[str] = field(default_factory=list)
    matched_temporal_refs: list[str] = field(default_factory=list)
    matched_columns: list[str] = field(default_factory=list)
    rejection_reason: Optional[str] = None


@dataclass
class FileSelectionResult:
    """
    Result of file selection process.
    
    Attributes:
        action: Action to take (auto_select, clarify, low_confidence).
        selected_file: Auto-selected file if action is AUTO_SELECT.
        candidates: Top candidates for user selection.
        rejected_files: Files that were rejected with reasons (Requirement 4.8).
        explanations: Detailed explanations for all ranked files.
        message: Human-readable message about the selection.
        top_confidence: Confidence score of the top-ranked file.
    """
    action: SelectionAction
    selected_file: Optional[FileCandidate] = None
    candidates: list[FileCandidate] = field(default_factory=list)
    rejected_files: list[FileCandidate] = field(default_factory=list)
    explanations: dict[str, FileRankingExplanation] = field(default_factory=dict)
    message: str = ""
    top_confidence: float = 0.0


# =============================================================================
# Temporal Reference Patterns
# =============================================================================


# Patterns for detecting temporal references in queries (Requirement 4.5)
TEMPORAL_PATTERNS = [
    # Month Year: "January 2024", "Jan 2024"
    (
        r'\b(January|February|March|April|May|June|July|August|September|'
        r'October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|'
        r'Sept|Oct|Nov|Dec)\s*(\d{4})\b',
        "month_year"
    ),
    # Quarter: "Q1 2024", "Q1", "first quarter"
    (r'\b[Qq]([1-4])\s*(\d{4})?\b', "quarter"),
    (r'\b(first|second|third|fourth)\s+quarter\b', "quarter_text"),
    # Year: "2024", "FY2024"
    (r'\b(?:FY)?(\d{4})\b', "year"),
    # Relative: "last month", "this year", "past 6 months"
    (r'\b(last|this|past|previous|current)\s+(month|year|quarter|week)\b', "relative"),
    # Date range: "2024-01", "01/2024"
    (r'\b(\d{4})[-/](\d{1,2})\b', "year_month"),
    (r'\b(\d{1,2})[-/](\d{4})\b', "month_year_alt"),
]


# =============================================================================
# FileSelector Implementation
# =============================================================================


class FileSelector:
    """
    Ranks and selects files based on semantic similarity, metadata matching,
    and user preference history.
    
    Implements the smart file selection algorithm with:
    - Weighted scoring: semantic (50%), metadata (30%), preference (20%)
    - Threshold behavior: auto-select >0.9, clarify 0.5-0.9, low-confidence <0.5
    - Temporal reference boosting for date patterns
    - User selection recording for preference learning
    - Explainability for ranking decisions
    
    Supports Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8.
    
    Example:
        >>> config = FileSelectorConfig()
        >>> selector = FileSelector(
        ...     embedding_service=embedding_svc,
        ...     preference_store=pref_store,
        ...     file_metadata=file_meta,
        ...     config=config
        ... )
        >>> result = selector.rank_files("What were sales in Q1 2024?")
        >>> if result.action == SelectionAction.AUTO_SELECT:
        ...     selected = result.selected_file
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingServiceProtocol,
        preference_store: PreferenceStoreProtocol,
        file_metadata: FileMetadataProtocol,
        config: Optional[FileSelectorConfig] = None
    ) -> None:
        """
        Initialize FileSelector with injected dependencies.
        
        Args:
            embedding_service: Service for computing semantic similarity.
            preference_store: Store for user preferences.
            file_metadata: Provider for file metadata.
            config: Optional configuration (uses defaults if not provided).
            
        Raises:
            ValueError: If any required dependency is None.
        """
        if embedding_service is None:
            raise ValueError("embedding_service is required")
        if preference_store is None:
            raise ValueError("preference_store is required")
        if file_metadata is None:
            raise ValueError("file_metadata is required")
        
        self._embedding_service = embedding_service
        self._preference_store = preference_store
        self._file_metadata = file_metadata
        self._config = config or FileSelectorConfig()
        
        logger.info(
            f"FileSelector initialized with weights: "
            f"semantic={self._config.semantic_weight}, "
            f"metadata={self._config.metadata_weight}, "
            f"preference={self._config.preference_weight}"
        )

    def rank_files(
        self,
        query: str,
        user_id: Optional[str] = None
    ) -> FileSelectionResult:
        """
        Rank all indexed files by relevance to the query.
        
        Implements Requirement 4.1: Rank files using semantic similarity (50%),
        metadata matching (30%), and user preference history (20%).
        
        Args:
            query: Natural language query.
            user_id: Optional user identifier for preference lookup.
            
        Returns:
            FileSelectionResult with ranked candidates and selection action.
            
        Raises:
            SelectionError: If no files are indexed or ranking fails.
        """
        logger.info(f"Ranking files for query: {query[:100]}...")
        
        # Get all indexed files
        indexed_files = self._file_metadata.get_all_indexed_files()
        
        if not indexed_files:
            logger.warning("No indexed files available for selection")
            raise SelectionError(
                "No indexed files available. Please index files first.",
                details={"query": query}
            )
        
        # Extract temporal references from query (Requirement 4.5)
        temporal_refs = self._extract_temporal_references(query)
        logger.debug(f"Extracted temporal references: {temporal_refs}")
        
        # Compute query embedding
        query_embedding = self._embedding_service.embed_text(query)
        
        # Score each file
        candidates: list[FileCandidate] = []
        explanations: dict[str, FileRankingExplanation] = {}
        
        for file_info in indexed_files:
            file_id = file_info.get("file_id", "")
            file_name = file_info.get("file_name", "")
            
            try:
                candidate, explanation = self._score_file(
                    file_info=file_info,
                    query=query,
                    query_embedding=query_embedding,
                    temporal_refs=temporal_refs,
                    user_id=user_id
                )
                candidates.append(candidate)
                explanations[file_id] = explanation
                
            except Exception as e:
                logger.warning(f"Error scoring file {file_name}: {e}")
                # Create rejected candidate
                candidate = FileCandidate(
                    file_id=file_id,
                    file_name=file_name,
                    semantic_score=0.0,
                    metadata_score=0.0,
                    preference_score=0.0,
                    combined_score=0.0,
                    rejection_reason=f"Scoring error: {str(e)}"
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

    def _score_file(
        self,
        file_info: dict[str, Any],
        query: str,
        query_embedding: list[float],
        temporal_refs: list[dict[str, Any]],
        user_id: Optional[str]
    ) -> tuple[FileCandidate, FileRankingExplanation]:
        """
        Score a single file against the query.
        
        Args:
            file_info: File metadata dictionary.
            query: Original query text.
            query_embedding: Pre-computed query embedding.
            temporal_refs: Extracted temporal references.
            user_id: Optional user identifier.
            
        Returns:
            Tuple of (FileCandidate, FileRankingExplanation).
        """
        file_id = file_info.get("file_id", "")
        file_name = file_info.get("file_name", "")
        file_path = file_info.get("file_path", "")
        
        ranking_reasons: list[str] = []
        matched_temporal: list[str] = []
        matched_columns: list[str] = []
        
        # 1. Compute semantic similarity score (Requirement 4.1 - 50% weight)
        semantic_score = self._compute_semantic_score(
            file_info=file_info,
            query_embedding=query_embedding
        )
        if semantic_score > 0.7:
            ranking_reasons.append(f"High semantic similarity ({semantic_score:.2f})")
        
        # 2. Compute metadata matching score (Requirement 4.1 - 30% weight)
        metadata_score, meta_reasons, meta_columns = self._compute_metadata_score(
            file_info=file_info,
            query=query
        )
        ranking_reasons.extend(meta_reasons)
        matched_columns.extend(meta_columns)
        
        # 3. Compute preference score (Requirement 4.1 - 20% weight)
        preference_score = self._preference_store.get_preference_score(
            query=query,
            file_id=file_id,
            user_id=user_id
        )
        if preference_score > 0.5:
            ranking_reasons.append(f"Previously selected for similar queries ({preference_score:.2f})")
        
        # 4. Apply temporal boosting (Requirement 4.5)
        temporal_boost, temporal_matches = self._compute_temporal_boost(
            file_name=file_name,
            file_path=file_path,
            temporal_refs=temporal_refs
        )
        matched_temporal.extend(temporal_matches)
        if temporal_boost > 0:
            ranking_reasons.append(f"Temporal match boost (+{temporal_boost:.2f})")
        
        # 5. Compute weighted combined score
        weighted_semantic = semantic_score * self._config.semantic_weight
        weighted_metadata = metadata_score * self._config.metadata_weight
        weighted_preference = preference_score * self._config.preference_weight
        
        combined_score = weighted_semantic + weighted_metadata + weighted_preference
        
        # Apply temporal boost (additive, capped at 1.0)
        combined_score = min(1.0, combined_score + temporal_boost)
        
        # Create score breakdown
        score_breakdown = ScoreBreakdown(
            semantic_score=semantic_score,
            metadata_score=metadata_score,
            preference_score=preference_score,
            temporal_boost=temporal_boost,
            weighted_semantic=weighted_semantic,
            weighted_metadata=weighted_metadata,
            weighted_preference=weighted_preference
        )
        
        # Determine rejection reason if score is very low
        rejection_reason: Optional[str] = None
        if combined_score < 0.2:
            if semantic_score < 0.3:
                rejection_reason = "Low semantic similarity to query"
            elif metadata_score < 0.2:
                rejection_reason = "No matching columns or metadata"
            else:
                rejection_reason = "Overall low relevance score"
        
        # Create candidate
        candidate = FileCandidate(
            file_id=file_id,
            file_name=file_name,
            semantic_score=semantic_score,
            metadata_score=metadata_score,
            preference_score=preference_score,
            combined_score=combined_score,
            rejection_reason=rejection_reason
        )
        
        # Create explanation
        explanation = FileRankingExplanation(
            file_id=file_id,
            file_name=file_name,
            combined_score=combined_score,
            score_breakdown=score_breakdown,
            ranking_reasons=ranking_reasons,
            matched_temporal_refs=matched_temporal,
            matched_columns=matched_columns,
            rejection_reason=rejection_reason
        )
        
        logger.debug(
            f"Scored file '{file_name}': combined={combined_score:.3f} "
            f"(semantic={semantic_score:.3f}, metadata={metadata_score:.3f}, "
            f"preference={preference_score:.3f}, temporal_boost={temporal_boost:.3f})"
        )
        
        return candidate, explanation

    def _compute_semantic_score(
        self,
        file_info: dict[str, Any],
        query_embedding: list[float]
    ) -> float:
        """
        Compute semantic similarity between query and file.
        
        Args:
            file_info: File metadata with optional embedding.
            query_embedding: Query embedding vector.
            
        Returns:
            Semantic similarity score (0.0 to 1.0).
        """
        # Try to get pre-computed file embedding
        file_id = file_info.get("file_id", "")
        file_embedding = self._file_metadata.get_file_embedding(file_id)
        
        if file_embedding is None:
            # Fall back to embedding file name and path
            file_text = f"{file_info.get('file_name', '')} {file_info.get('file_path', '')}"
            columns = file_info.get("columns", [])
            if columns:
                file_text += " " + " ".join(columns)
            
            file_embedding = self._embedding_service.embed_text(file_text)
        
        # Compute cosine similarity
        return self._embedding_service.compute_similarity(query_embedding, file_embedding)
    
    def _compute_metadata_score(
        self,
        file_info: dict[str, Any],
        query: str
    ) -> tuple[float, list[str], list[str]]:
        """
        Compute metadata matching score.
        
        Checks for matches in file name, path, column names, and sheet names.
        
        Args:
            file_info: File metadata dictionary.
            query: Query text.
            
        Returns:
            Tuple of (score, reasons, matched_columns).
        """
        score = 0.0
        reasons: list[str] = []
        matched_columns: list[str] = []
        
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # Check file name match
        file_name = file_info.get("file_name", "").lower()
        file_name_words = set(re.split(r'[_\-\s.]+', file_name))
        name_overlap = query_words & file_name_words
        if name_overlap:
            name_score = len(name_overlap) / max(len(query_words), 1)
            score += name_score * 0.3
            reasons.append(f"File name contains: {', '.join(name_overlap)}")
        
        # Check column name matches
        columns = file_info.get("columns", [])
        for col in columns:
            col_lower = col.lower()
            if col_lower in query_lower or any(w in col_lower for w in query_words):
                matched_columns.append(col)
        
        if matched_columns:
            col_score = min(1.0, len(matched_columns) / 3)
            score += col_score * 0.4
            reasons.append(f"Matching columns: {', '.join(matched_columns[:3])}")
        
        # Check sheet name matches
        sheets = file_info.get("sheet_names", [])
        matched_sheets = [s for s in sheets if s.lower() in query_lower]
        if matched_sheets:
            score += 0.2
            reasons.append(f"Matching sheets: {', '.join(matched_sheets)}")
        
        # Check path components
        file_path = file_info.get("file_path", "").lower()
        path_parts = set(re.split(r'[/\\]+', file_path))
        path_overlap = query_words & path_parts
        if path_overlap:
            score += 0.1
            reasons.append(f"Path contains: {', '.join(path_overlap)}")
        
        return min(1.0, score), reasons, matched_columns

    def _compute_temporal_boost(
        self,
        file_name: str,
        file_path: str,
        temporal_refs: list[dict[str, Any]]
    ) -> tuple[float, list[str]]:
        """
        Compute temporal boost for files matching date patterns in query.
        
        Implements Requirement 4.5: Boost scores for files with matching dates.
        
        Args:
            file_name: Name of the file.
            file_path: Path to the file.
            temporal_refs: Temporal references extracted from query.
            
        Returns:
            Tuple of (boost_value, matched_references).
        """
        if not temporal_refs:
            return 0.0, []
        
        matched_refs: list[str] = []
        file_text = f"{file_name} {file_path}".lower()
        
        for ref in temporal_refs:
            ref_type = ref.get("type", "")
            ref_value = ref.get("value", "")
            ref_text = ref.get("text", "")
            
            matched = False
            
            if ref_type == "month_year":
                # Check for month and year in file name
                month = ref.get("month", "")
                year = ref.get("year", "")
                if month.lower() in file_text and year in file_text:
                    matched = True
                # Also check abbreviated month
                month_abbrev = month[:3].lower() if len(month) > 3 else month.lower()
                if month_abbrev in file_text and year in file_text:
                    matched = True
            
            elif ref_type == "quarter":
                # Check for Q1, Q2, etc.
                quarter = ref.get("quarter", "")
                year = ref.get("year", "")
                if quarter.lower() in file_text:
                    if not year or year in file_text:
                        matched = True
            
            elif ref_type == "year":
                year = ref.get("year", ref_value)
                if year in file_text:
                    matched = True
            
            elif ref_type in ("year_month", "month_year_alt"):
                # Check for YYYY-MM or MM-YYYY patterns
                if ref_value in file_text:
                    matched = True
            
            if matched:
                matched_refs.append(ref_text)
        
        # Calculate boost based on number of matches
        if not matched_refs:
            return 0.0, []
        
        # More matches = higher boost, capped at temporal_boost_factor
        boost = min(
            self._config.temporal_boost_factor,
            len(matched_refs) * (self._config.temporal_boost_factor / 2)
        )
        
        return boost, matched_refs
    
    def _extract_temporal_references(self, query: str) -> list[dict[str, Any]]:
        """
        Extract temporal references from query text.
        
        Implements Requirement 4.5: Detect temporal references like
        "January 2024", "Q3", etc.
        
        Args:
            query: Query text.
            
        Returns:
            List of temporal reference dictionaries.
        """
        temporal_refs: list[dict[str, Any]] = []
        
        for pattern, ref_type in TEMPORAL_PATTERNS:
            matches = re.finditer(pattern, query, re.IGNORECASE)
            
            for match in matches:
                ref: dict[str, Any] = {
                    "type": ref_type,
                    "text": match.group(0),
                    "value": match.group(0)
                }
                
                if ref_type == "month_year":
                    ref["month"] = match.group(1)
                    ref["year"] = match.group(2)
                
                elif ref_type == "quarter":
                    ref["quarter"] = f"Q{match.group(1)}"
                    ref["year"] = match.group(2) if match.lastindex >= 2 else ""
                
                elif ref_type == "quarter_text":
                    quarter_map = {"first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4"}
                    ref["quarter"] = quarter_map.get(match.group(1).lower(), "")
                
                elif ref_type == "year":
                    ref["year"] = match.group(1)
                
                elif ref_type == "year_month":
                    ref["year"] = match.group(1)
                    ref["month"] = match.group(2)
                
                elif ref_type == "month_year_alt":
                    ref["month"] = match.group(1)
                    ref["year"] = match.group(2)
                
                temporal_refs.append(ref)
        
        return temporal_refs

    def _determine_selection_action(
        self,
        candidates: list[FileCandidate],
        explanations: dict[str, FileRankingExplanation],
        query: str
    ) -> FileSelectionResult:
        """
        Determine selection action based on confidence thresholds.
        
        Implements Requirements 4.2, 4.3, 4.4:
        - 4.2: Auto-select when confidence > 0.9
        - 4.3: Present top 3 candidates when confidence 0.5-0.9
        - 4.4: Request clarification when confidence < 0.5
        
        Args:
            candidates: Sorted list of file candidates.
            explanations: Explanations for each file.
            query: Original query.
            
        Returns:
            FileSelectionResult with appropriate action.
        """
        if not candidates:
            return FileSelectionResult(
                action=SelectionAction.LOW_CONFIDENCE,
                message="No files available for selection.",
                top_confidence=0.0
            )
        
        top_candidate = candidates[0]
        top_confidence = top_candidate.combined_score
        
        # Separate accepted and rejected candidates
        accepted = [c for c in candidates if c.rejection_reason is None]
        rejected = [c for c in candidates if c.rejection_reason is not None]
        
        # Requirement 4.2: Auto-select when confidence > 0.9
        if top_confidence > self._config.auto_select_threshold:
            logger.info(
                f"Auto-selecting file '{top_candidate.file_name}' "
                f"with confidence {top_confidence:.3f}"
            )
            return FileSelectionResult(
                action=SelectionAction.AUTO_SELECT,
                selected_file=top_candidate,
                candidates=[top_candidate],
                rejected_files=rejected,
                explanations=explanations,
                message=f"Automatically selected '{top_candidate.file_name}' "
                        f"with high confidence ({top_confidence:.2f}).",
                top_confidence=top_confidence
            )
        
        # Requirement 4.3: Present top 3 candidates when confidence 0.5-0.9
        if top_confidence >= self._config.clarify_threshold:
            top_candidates = accepted[:self._config.max_candidates]
            logger.info(
                f"Presenting {len(top_candidates)} candidates for clarification "
                f"(top confidence: {top_confidence:.3f})"
            )
            return FileSelectionResult(
                action=SelectionAction.CLARIFY,
                candidates=top_candidates,
                rejected_files=rejected,
                explanations=explanations,
                message=f"Multiple files match your query. Please select one "
                        f"(top confidence: {top_confidence:.2f}).",
                top_confidence=top_confidence
            )
        
        # Requirement 4.4: Request clarification when confidence < 0.5
        logger.info(
            f"Low confidence ({top_confidence:.3f}), requesting clarification"
        )
        return FileSelectionResult(
            action=SelectionAction.LOW_CONFIDENCE,
            candidates=accepted[:self._config.max_candidates],
            rejected_files=rejected,
            explanations=explanations,
            message=f"No files match your query with high confidence "
                    f"(best match: {top_confidence:.2f}). "
                    f"Please clarify which file you want to query.",
            top_confidence=top_confidence
        )

    def record_user_selection(
        self,
        query: str,
        file_id: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Record user's file selection for preference learning.
        
        Implements Requirement 4.6: Record user file selections to improve
        future preference-based ranking.
        
        Args:
            query: Query that led to selection.
            file_id: ID of selected file.
            user_id: Optional user identifier.
            
        Returns:
            True if recording succeeded.
        """
        logger.info(f"Recording user selection: file_id={file_id}, query={query[:50]}...")
        
        try:
            success = self._preference_store.record_selection(
                query=query,
                file_id=file_id,
                user_id=user_id
            )
            
            if success:
                logger.debug(f"Successfully recorded selection for file {file_id}")
            else:
                logger.warning(f"Failed to record selection for file {file_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error recording user selection: {e}", exc_info=True)
            return False
    
    def get_explanation(
        self,
        result: FileSelectionResult,
        file_id: str
    ) -> Optional[FileRankingExplanation]:
        """
        Get detailed explanation for a specific file's ranking.
        
        Implements Requirement 4.7: Provide explainability for ranking decisions.
        
        Args:
            result: File selection result.
            file_id: File to get explanation for.
            
        Returns:
            FileRankingExplanation or None if not found.
        """
        return result.explanations.get(file_id)
    
    def get_rejection_reasons(
        self,
        result: FileSelectionResult
    ) -> list[tuple[str, str]]:
        """
        Get rejection reasons for all rejected files.
        
        Implements Requirement 4.8: Include rejected files with reasons.
        
        Args:
            result: File selection result.
            
        Returns:
            List of (file_name, rejection_reason) tuples.
        """
        return [
            (f.file_name, f.rejection_reason or "Unknown reason")
            for f in result.rejected_files
        ]
    
    def format_explanation_text(
        self,
        explanation: FileRankingExplanation
    ) -> str:
        """
        Format explanation as human-readable text.
        
        Args:
            explanation: File ranking explanation.
            
        Returns:
            Formatted explanation string.
        """
        lines = [
            f"File: {explanation.file_name}",
            f"Combined Score: {explanation.combined_score:.3f}",
            "",
            "Score Breakdown:",
            f"  - Semantic: {explanation.score_breakdown.semantic_score:.3f} "
            f"(weighted: {explanation.score_breakdown.weighted_semantic:.3f})",
            f"  - Metadata: {explanation.score_breakdown.metadata_score:.3f} "
            f"(weighted: {explanation.score_breakdown.weighted_metadata:.3f})",
            f"  - Preference: {explanation.score_breakdown.preference_score:.3f} "
            f"(weighted: {explanation.score_breakdown.weighted_preference:.3f})",
        ]
        
        if explanation.score_breakdown.temporal_boost > 0:
            lines.append(
                f"  - Temporal Boost: +{explanation.score_breakdown.temporal_boost:.3f}"
            )
        
        if explanation.ranking_reasons:
            lines.append("")
            lines.append("Ranking Reasons:")
            for reason in explanation.ranking_reasons:
                lines.append(f"  • {reason}")
        
        if explanation.matched_temporal_refs:
            lines.append("")
            lines.append(f"Matched Temporal References: {', '.join(explanation.matched_temporal_refs)}")
        
        if explanation.matched_columns:
            lines.append(f"Matched Columns: {', '.join(explanation.matched_columns)}")
        
        if explanation.rejection_reason:
            lines.append("")
            lines.append(f"Rejection Reason: {explanation.rejection_reason}")
        
        return "\n".join(lines)
