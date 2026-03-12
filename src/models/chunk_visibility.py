"""
Chunk visibility models for debugging and inspection.

This module defines the data models used for chunk visibility and debugging
capabilities including:
- ChunkDetails: Complete chunk information for debugging
- ExtractionMetadata: Metadata about the extraction process
- ChunkVersion: Versioned chunk records for tracking re-indexing
- ChunkFilters: Filters for chunk search and filtering
- PaginatedChunkResponse: Paginated response for chunk listings
- ChunkFeedback: User feedback on chunk quality

These models support Requirements 1.1, 1.2, 1.3, 1.6, 1.7, 3.1, 3.5.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


@dataclass
class ChunkDetails:
    """
    Complete chunk information for debugging.
    
    Contains all details about a chunk including its content, boundaries,
    extraction strategy, and embedding metadata.
    
    Attributes:
        chunk_id: Unique identifier for the chunk.
        file_id: ID of the file this chunk belongs to.
        file_name: Name of the source file.
        sheet_name: Name of the sheet this chunk is from.
        chunk_index: Index of this chunk within the file/sheet.
        chunk_text: The processed chunk text content.
        raw_source_data: The raw source data before processing.
        start_row: Starting row number of the chunk.
        end_row: Ending row number of the chunk.
        overlap_rows: Number of rows overlapping with adjacent chunks.
        extraction_strategy: Strategy used for extraction (openpyxl, docling, etc.).
        content_type: Type of content in the chunk (data, headers, metadata).
        row_count: Number of rows in the chunk.
        column_count: Number of columns in the chunk.
        embedding_dimensions: Dimensions of the embedding vector.
        token_count: Number of tokens in the chunk text.
        embedding_model: Name of the embedding model used.
        similarity_score: Optional similarity score when returned from search.
    
    Supports Requirements 1.1, 1.2, 1.3, 1.6, 1.7.
    """
    chunk_id: str
    file_id: str
    file_name: str
    sheet_name: str
    chunk_index: int
    chunk_text: str
    raw_source_data: str
    start_row: int
    end_row: int
    overlap_rows: int
    extraction_strategy: str
    content_type: str
    row_count: int
    column_count: int
    embedding_dimensions: int
    token_count: int
    embedding_model: str
    similarity_score: Optional[float] = None
    
    def __post_init__(self) -> None:
        """Validate chunk details after initialization."""
        if self.chunk_index < 0:
            raise ValueError(f"chunk_index must be non-negative, got {self.chunk_index}")
        if self.start_row < 0:
            raise ValueError(f"start_row must be non-negative, got {self.start_row}")
        if self.end_row < self.start_row:
            raise ValueError(
                f"end_row ({self.end_row}) must be >= start_row ({self.start_row})"
            )
        if self.overlap_rows < 0:
            raise ValueError(f"overlap_rows must be non-negative, got {self.overlap_rows}")
        if self.row_count < 0:
            raise ValueError(f"row_count must be non-negative, got {self.row_count}")
        if self.column_count < 0:
            raise ValueError(f"column_count must be non-negative, got {self.column_count}")
        if self.embedding_dimensions <= 0:
            raise ValueError(
                f"embedding_dimensions must be positive, got {self.embedding_dimensions}"
            )
        if self.token_count < 0:
            raise ValueError(f"token_count must be non-negative, got {self.token_count}")
        if self.similarity_score is not None and not 0.0 <= self.similarity_score <= 1.0:
            raise ValueError(
                f"similarity_score must be between 0.0 and 1.0, got {self.similarity_score}"
            )


@dataclass
class ExtractionMetadata:
    """
    Metadata about the extraction process for a file.
    
    Contains details about which extraction strategy was used, quality metrics,
    and any errors or warnings encountered during extraction.
    
    Attributes:
        file_id: ID of the file this metadata belongs to.
        strategy_used: The extraction strategy that was used.
        strategy_selected_reason: Reason why this strategy was selected (for auto mode).
        complexity_score: Complexity score that triggered strategy selection.
        quality_score: Overall quality score of the extraction (0.0 to 1.0).
        has_headers: Whether headers were detected in the data.
        has_data: Whether actual data rows were found.
        data_completeness: Completeness score of extracted data (0.0 to 1.0).
        structure_clarity: Clarity score of data structure (0.0 to 1.0).
        extraction_errors: List of errors encountered during extraction.
        extraction_warnings: List of warnings generated during extraction.
        fallback_used: Whether a fallback strategy was used.
        fallback_reason: Reason for using fallback strategy.
        extraction_duration_ms: Duration of extraction in milliseconds.
        extracted_at: Timestamp when extraction was performed.
    
    Supports Requirements 3.1, 3.5.
    """
    file_id: str
    strategy_used: str
    strategy_selected_reason: Optional[str]
    complexity_score: Optional[float]
    quality_score: float
    has_headers: bool
    has_data: bool
    data_completeness: float
    structure_clarity: float
    extraction_errors: list[str] = field(default_factory=list)
    extraction_warnings: list[str] = field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    extraction_duration_ms: int = 0
    extracted_at: str = ""
    
    def __post_init__(self) -> None:
        """Validate extraction metadata after initialization."""
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError(
                f"quality_score must be between 0.0 and 1.0, got {self.quality_score}"
            )
        if not 0.0 <= self.data_completeness <= 1.0:
            raise ValueError(
                f"data_completeness must be between 0.0 and 1.0, got {self.data_completeness}"
            )
        if not 0.0 <= self.structure_clarity <= 1.0:
            raise ValueError(
                f"structure_clarity must be between 0.0 and 1.0, got {self.structure_clarity}"
            )
        if self.complexity_score is not None and not 0.0 <= self.complexity_score <= 1.0:
            raise ValueError(
                f"complexity_score must be between 0.0 and 1.0, got {self.complexity_score}"
            )
        if self.extraction_duration_ms < 0:
            raise ValueError(
                f"extraction_duration_ms must be non-negative, got {self.extraction_duration_ms}"
            )


@dataclass
class ChunkVersion:
    """
    Versioned chunk record for tracking re-indexing changes.
    
    Stores historical versions of chunks to enable comparison and
    rollback when files are re-indexed.
    
    Attributes:
        version_id: Unique identifier for this version.
        chunk_id: ID of the chunk this version belongs to.
        version_number: Sequential version number (1, 2, 3, ...).
        chunk_text: The chunk text content for this version.
        extraction_strategy: Strategy used for this version's extraction.
        indexed_at: Timestamp when this version was indexed.
        change_summary: Optional summary of changes from previous version.
    
    Supports Requirements 21.1, 21.2, 21.3, 21.4.
    """
    version_id: str
    chunk_id: str
    version_number: int
    chunk_text: str
    extraction_strategy: str
    indexed_at: datetime
    change_summary: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate chunk version after initialization."""
        if self.version_number < 1:
            raise ValueError(
                f"version_number must be >= 1, got {self.version_number}"
            )


@dataclass
class ChunkFilters:
    """
    Filters for chunk search and filtering.
    
    Used to filter chunks by various criteria. Multiple filters
    are combined using AND logic.
    
    Attributes:
        extraction_strategy: Filter by extraction strategy used.
        file_id: Filter by file ID.
        sheet_name: Filter by sheet name.
        content_type: Filter by content type.
        min_quality_score: Filter by minimum quality score.
    
    Supports Requirements 2.2, 2.3.
    """
    extraction_strategy: Optional[str] = None
    file_id: Optional[str] = None
    sheet_name: Optional[str] = None
    content_type: Optional[str] = None
    min_quality_score: Optional[float] = None
    
    def __post_init__(self) -> None:
        """Validate chunk filters after initialization."""
        if self.min_quality_score is not None:
            if not 0.0 <= self.min_quality_score <= 1.0:
                raise ValueError(
                    f"min_quality_score must be between 0.0 and 1.0, "
                    f"got {self.min_quality_score}"
                )
    
    def is_empty(self) -> bool:
        """
        Check if all filters are empty/None.
        
        Returns:
            True if no filters are set, False otherwise.
        """
        return (
            self.extraction_strategy is None
            and self.file_id is None
            and self.sheet_name is None
            and self.content_type is None
            and self.min_quality_score is None
        )
    
    def to_dict(self) -> dict[str, Optional[str | float]]:
        """
        Convert filters to a dictionary, excluding None values.
        
        Returns:
            Dictionary of non-None filter values.
        """
        result: dict[str, Optional[str | float]] = {}
        if self.extraction_strategy is not None:
            result["extraction_strategy"] = self.extraction_strategy
        if self.file_id is not None:
            result["file_id"] = self.file_id
        if self.sheet_name is not None:
            result["sheet_name"] = self.sheet_name
        if self.content_type is not None:
            result["content_type"] = self.content_type
        if self.min_quality_score is not None:
            result["min_quality_score"] = self.min_quality_score
        return result


class PaginatedChunkResponse(BaseModel):
    """
    Paginated response for chunk listings.
    
    Contains a page of chunks along with pagination metadata.
    
    Supports Requirements 1.5, 13.6.
    """
    chunks: list[dict] = Field(
        default_factory=list,
        description="List of chunk data dictionaries"
    )
    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of chunks matching the query"
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number (1-indexed)"
    )
    page_size: int = Field(
        ...,
        ge=1,
        le=100,
        description="Number of items per page (max 100)"
    )
    has_more: bool = Field(
        ...,
        description="Whether there are more pages available"
    )
    
    @field_validator('page_size')
    @classmethod
    def validate_page_size(cls, v: int) -> int:
        """Validate page_size is within allowed range."""
        if v < 1:
            raise ValueError("page_size must be at least 1")
        if v > 100:
            raise ValueError("page_size cannot exceed 100")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chunks": [
                    {
                        "chunk_id": "chunk_001",
                        "file_id": "file_123",
                        "file_name": "sales_2024.xlsx",
                        "sheet_name": "Q1",
                        "chunk_index": 0,
                        "chunk_text": "Month,Revenue,Expenses\nJan,10000,7000",
                        "start_row": 1,
                        "end_row": 50,
                        "extraction_strategy": "openpyxl"
                    }
                ],
                "total_count": 150,
                "page": 1,
                "page_size": 20,
                "has_more": True
            }
        }
    )


class ChunkFeedback(BaseModel):
    """
    User feedback on chunk quality.
    
    Allows users to report issues with chunks to improve
    extraction quality over time.
    
    Supports Requirements 27.1, 27.2.
    """
    chunk_id: str = Field(
        ...,
        description="ID of the chunk being reviewed"
    )
    feedback_type: str = Field(
        ...,
        description="Type of feedback: incorrect_data, missing_data, "
                    "wrong_boundaries, extraction_error, or other"
    )
    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Quality rating from 1 (poor) to 5 (excellent)"
    )
    comment: Optional[str] = Field(
        default=None,
        description="Optional detailed comment about the issue"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional user ID for tracking feedback source"
    )
    
    @field_validator('feedback_type')
    @classmethod
    def validate_feedback_type(cls, v: str) -> str:
        """Validate feedback_type is a valid value."""
        valid_types = {
            'incorrect_data',
            'missing_data',
            'wrong_boundaries',
            'extraction_error',
            'other'
        }
        if v not in valid_types:
            raise ValueError(
                f"feedback_type must be one of {valid_types}, got '{v}'"
            )
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chunk_id": "chunk_001",
                "feedback_type": "wrong_boundaries",
                "rating": 2,
                "comment": "Chunk splits a table in the middle of a data section",
                "user_id": "user_123"
            }
        }
    )
