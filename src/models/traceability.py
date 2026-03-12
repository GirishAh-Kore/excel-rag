"""
Traceability data models for the Smart Excel Query Pipeline.

This module defines the data models used for query tracing and data lineage
tracking, enabling complete audit trails from query to answer.

These models support Requirements 16.2 and 17.1:
- QueryTrace: Complete audit record of query processing decisions
- DataLineage: Links answer components to source cells
- FileSelectionDecision: Records file selection decisions
- SheetSelectionDecision: Records sheet selection decisions

All models follow SOLID principles with proper validation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.models.query_pipeline import (
    Citation,
    FileCandidate,
    QueryType,
    SheetCandidate,
)


@dataclass
class FileSelectionDecision:
    """
    Record of a file selection decision during query processing.
    
    Captures the candidates considered, the selected file, reasoning,
    and confidence for audit and debugging purposes.
    
    Attributes:
        candidates: List of file candidates that were evaluated.
        selected_file_id: ID of the file that was selected.
        reasoning: Explanation of why this file was selected.
        confidence: Confidence score for the selection (0.0 to 1.0).
        timestamp: When the selection decision was made.
    
    Supports Requirement 16.2: Record file_selection_decisions in QueryTrace.
    """
    candidates: list[FileCandidate]
    selected_file_id: str
    reasoning: str
    confidence: float
    timestamp: datetime
    
    def __post_init__(self) -> None:
        """Validate confidence is within valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        if not self.selected_file_id:
            raise ValueError("selected_file_id cannot be empty")
        if not self.reasoning:
            raise ValueError("reasoning cannot be empty")


@dataclass
class SheetSelectionDecision:
    """
    Record of a sheet selection decision during query processing.
    
    Captures the candidates considered, selected sheets, combination strategy,
    reasoning, and confidence for audit and debugging purposes.
    
    Attributes:
        candidates: List of sheet candidates that were evaluated.
        selected_sheets: List of sheet names that were selected.
        combination_strategy: How multiple sheets should be combined
            (union, join, separate), or None for single sheet.
        reasoning: Explanation of why these sheets were selected.
        confidence: Confidence score for the selection (0.0 to 1.0).
        timestamp: When the selection decision was made.
    
    Supports Requirement 16.2: Record sheet_selection_decisions in QueryTrace.
    """
    candidates: list[SheetCandidate]
    selected_sheets: list[str]
    combination_strategy: Optional[str]
    reasoning: str
    confidence: float
    timestamp: datetime
    
    def __post_init__(self) -> None:
        """Validate fields."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        if not self.selected_sheets:
            raise ValueError("selected_sheets cannot be empty")
        if not self.reasoning:
            raise ValueError("reasoning cannot be empty")
        
        valid_strategies = {"union", "join", "separate", None}
        if self.combination_strategy not in valid_strategies:
            raise ValueError(
                f"combination_strategy must be one of {valid_strategies}, "
                f"got '{self.combination_strategy}'"
            )


@dataclass
class QueryTrace:
    """
    Complete audit record of query processing.
    
    Contains all decisions made during query processing including file selection,
    sheet selection, query classification, data retrieval, and answer generation.
    This enables full traceability from query to answer for compliance and debugging.
    
    Attributes:
        trace_id: Unique identifier for this trace.
        query_text: The original query text submitted by the user.
        timestamp: ISO format timestamp when the query was received.
        user_id: Optional user identifier for audit purposes.
        session_id: Optional session identifier for conversation context.
        file_candidates: List of files considered during selection.
        file_selection_reasoning: Explanation of file selection decision.
        selected_file_id: ID of the file that was selected.
        file_confidence: Confidence in file selection (0.0 to 1.0).
        sheet_candidates: List of sheets considered during selection.
        sheet_selection_reasoning: Explanation of sheet selection decision.
        selected_sheets: List of sheet names that were selected.
        sheet_confidence: Confidence in sheet selection (0.0 to 1.0).
        query_type: Classified type of the query.
        classification_confidence: Confidence in query classification (0.0 to 1.0).
        chunks_retrieved: List of chunk IDs that were retrieved.
        retrieval_scores: Similarity scores for retrieved chunks.
        answer_text: The generated answer text.
        citations: Source citations for the answer.
        answer_confidence: Overall confidence in the answer (0.0 to 1.0).
        total_processing_time_ms: Total time to process the query in milliseconds.
        file_selection_time_ms: Time spent on file selection in milliseconds.
        sheet_selection_time_ms: Time spent on sheet selection in milliseconds.
        retrieval_time_ms: Time spent on chunk retrieval in milliseconds.
        generation_time_ms: Time spent on answer generation in milliseconds.
    
    Supports Requirement 16.2: Record QueryTrace containing query_text, timestamp,
    user_id, session_id, file_selection_decisions, sheet_selection_decisions,
    chunks_retrieved, answer_generated, and total_processing_time.
    """
    trace_id: str
    query_text: str
    timestamp: str
    user_id: Optional[str]
    session_id: Optional[str]
    
    # File selection
    file_candidates: list[FileCandidate] = field(default_factory=list)
    file_selection_reasoning: str = ""
    selected_file_id: str = ""
    file_confidence: float = 0.0
    
    # Sheet selection
    sheet_candidates: list[SheetCandidate] = field(default_factory=list)
    sheet_selection_reasoning: str = ""
    selected_sheets: list[str] = field(default_factory=list)
    sheet_confidence: float = 0.0
    
    # Query classification
    query_type: Optional[QueryType] = None
    classification_confidence: float = 0.0
    
    # Data retrieval
    chunks_retrieved: list[str] = field(default_factory=list)
    retrieval_scores: list[float] = field(default_factory=list)
    
    # Answer generation
    answer_text: str = ""
    citations: list[Citation] = field(default_factory=list)
    answer_confidence: float = 0.0
    
    # Performance metrics
    total_processing_time_ms: int = 0
    file_selection_time_ms: int = 0
    sheet_selection_time_ms: int = 0
    retrieval_time_ms: int = 0
    generation_time_ms: int = 0
    
    def __post_init__(self) -> None:
        """Validate required fields and confidence scores."""
        if not self.trace_id:
            raise ValueError("trace_id cannot be empty")
        if not self.query_text:
            raise ValueError("query_text cannot be empty")
        if not self.timestamp:
            raise ValueError("timestamp cannot be empty")
        
        # Validate all confidence scores
        confidence_fields = [
            ("file_confidence", self.file_confidence),
            ("sheet_confidence", self.sheet_confidence),
            ("classification_confidence", self.classification_confidence),
            ("answer_confidence", self.answer_confidence),
        ]
        for field_name, value in confidence_fields:
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{field_name} must be between 0.0 and 1.0, got {value}"
                )
        
        # Validate all retrieval scores
        for i, score in enumerate(self.retrieval_scores):
            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    f"retrieval_scores[{i}] must be between 0.0 and 1.0, got {score}"
                )
        
        # Validate timing fields are non-negative
        timing_fields = [
            ("total_processing_time_ms", self.total_processing_time_ms),
            ("file_selection_time_ms", self.file_selection_time_ms),
            ("sheet_selection_time_ms", self.sheet_selection_time_ms),
            ("retrieval_time_ms", self.retrieval_time_ms),
            ("generation_time_ms", self.generation_time_ms),
        ]
        for field_name, value in timing_fields:
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative, got {value}")


@dataclass
class DataLineage:
    """
    Complete data path from source cell to answer component.
    
    Tracks the lineage of data from its source in an Excel file through
    the indexing and retrieval process to its use in an answer. This enables
    compliance officers to verify data accuracy and meet audit requirements.
    
    Attributes:
        lineage_id: Unique identifier for this lineage record.
        answer_component: The part of the answer this lineage relates to.
        file_id: ID of the source file.
        file_name: Name of the source file.
        sheet_name: Name of the source sheet.
        cell_range: Cell range containing the source data (e.g., "A1:B10").
        source_value: The actual value from the source cell(s).
        chunk_id: ID of the chunk containing this data.
        embedding_id: ID of the embedding for this chunk.
        retrieval_score: Similarity score when this chunk was retrieved (0.0 to 1.0).
        indexed_at: ISO format timestamp when the source data was indexed.
        last_verified_at: ISO format timestamp when lineage was last verified,
            or None if never verified.
        is_stale: Whether the source data may have changed since indexing.
        stale_reason: Explanation of why data is considered stale, or None.
    
    Supports Requirement 17.1: Maintain DataLineage records linking each answer
    component to source: file_id, sheet_name, cell_range, chunk_id, embedding_id.
    """
    lineage_id: str
    answer_component: str
    file_id: str
    file_name: str
    sheet_name: str
    cell_range: str
    source_value: str
    chunk_id: str
    embedding_id: str
    retrieval_score: float
    indexed_at: str
    last_verified_at: Optional[str]
    is_stale: bool
    stale_reason: Optional[str]
    
    def __post_init__(self) -> None:
        """Validate required fields and scores."""
        required_fields = [
            ("lineage_id", self.lineage_id),
            ("answer_component", self.answer_component),
            ("file_id", self.file_id),
            ("file_name", self.file_name),
            ("sheet_name", self.sheet_name),
            ("cell_range", self.cell_range),
            ("chunk_id", self.chunk_id),
            ("embedding_id", self.embedding_id),
            ("indexed_at", self.indexed_at),
        ]
        for field_name, value in required_fields:
            if not value:
                raise ValueError(f"{field_name} cannot be empty")
        
        if not 0.0 <= self.retrieval_score <= 1.0:
            raise ValueError(
                f"retrieval_score must be between 0.0 and 1.0, "
                f"got {self.retrieval_score}"
            )
        
        # If stale, must have a reason
        if self.is_stale and not self.stale_reason:
            raise ValueError("stale_reason is required when is_stale is True")
