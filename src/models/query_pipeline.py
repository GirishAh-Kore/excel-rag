"""
Core data models for the Smart Excel Query Pipeline.

This module defines the data models used throughout the query pipeline including:
- Query classification types and results
- File and sheet selection candidates
- Citations and confidence scoring
- Query responses and clarification requests

These models support Requirements 6.1, 11.1, 11.2, 11.4, and 11.8.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class QueryType(str, Enum):
    """
    Classification of query types for the smart query pipeline.
    
    Supports Requirement 6.1: Query classification into aggregation,
    lookup, summarization, or comparison.
    """
    AGGREGATION = "aggregation"
    LOOKUP = "lookup"
    SUMMARIZATION = "summarization"
    COMPARISON = "comparison"


@dataclass
class QueryClassification:
    """
    Result of query classification.
    
    Contains the classified query type, confidence score, and extracted
    parameters like aggregations, filters, and columns detected in the query.
    
    Attributes:
        query_type: The primary classified query type.
        confidence: Confidence score for the classification (0.0 to 1.0).
        alternative_types: Alternative classifications with their confidence scores,
            populated when primary confidence is below 0.6.
        detected_aggregations: Aggregation functions detected (SUM, AVG, etc.).
        detected_filters: Filter conditions detected in the query.
        detected_columns: Column names detected in the query.
    
    Supports Requirement 6.1, 6.6, 6.7.
    """
    query_type: QueryType
    confidence: float
    alternative_types: list[tuple[QueryType, float]] = field(default_factory=list)
    detected_aggregations: list[str] = field(default_factory=list)
    detected_filters: list[str] = field(default_factory=list)
    detected_columns: list[str] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Validate confidence is within valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class FileCandidate:
    """
    A file candidate during file selection.
    
    Represents a file being considered for query processing with its
    various scoring components.
    
    Attributes:
        file_id: Unique identifier for the file.
        file_name: Name of the file.
        semantic_score: Score from semantic similarity matching (0.0 to 1.0).
        metadata_score: Score from metadata matching (0.0 to 1.0).
        preference_score: Score from user preference history (0.0 to 1.0).
        combined_score: Weighted combination of all scores (0.0 to 1.0).
        rejection_reason: Reason if file was rejected from selection.
    
    Supports Requirement 4.1, 4.7, 4.8.
    """
    file_id: str
    file_name: str
    semantic_score: float
    metadata_score: float
    preference_score: float
    combined_score: float
    rejection_reason: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate all scores are within valid range."""
        for score_name in ['semantic_score', 'metadata_score', 'preference_score', 'combined_score']:
            score_value = getattr(self, score_name)
            if not 0.0 <= score_value <= 1.0:
                raise ValueError(f"{score_name} must be between 0.0 and 1.0, got {score_value}")


@dataclass
class SheetCandidate:
    """
    A sheet candidate during sheet selection.
    
    Represents a sheet being considered for query processing with its
    various scoring components.
    
    Attributes:
        sheet_name: Name of the sheet.
        name_score: Score from sheet name similarity (0.0 to 1.0).
        header_score: Score from header/column matching (0.0 to 1.0).
        data_type_score: Score from data type alignment (0.0 to 1.0).
        content_score: Score from content similarity (0.0 to 1.0).
        combined_score: Weighted combination of all scores (0.0 to 1.0).
    
    Supports Requirement 5.1, 5.6.
    """
    sheet_name: str
    name_score: float
    header_score: float
    data_type_score: float
    content_score: float
    combined_score: float
    
    def __post_init__(self) -> None:
        """Validate all scores are within valid range."""
        for score_name in ['name_score', 'header_score', 'data_type_score', 'content_score', 'combined_score']:
            score_value = getattr(self, score_name)
            if not 0.0 <= score_value <= 1.0:
                raise ValueError(f"{score_name} must be between 0.0 and 1.0, got {score_value}")


@dataclass
class Citation:
    """
    Source citation for an answer.
    
    Links an answer component back to its source data in the Excel file.
    Format follows Requirement 11.2: [File: filename, Sheet: sheetname, Range: cellrange].
    
    Attributes:
        file_name: Name of the source file.
        sheet_name: Name of the source sheet.
        cell_range: Cell range containing the source data (e.g., "A1:B10").
        lineage_id: Unique identifier for data lineage tracking.
        source_value: Optional actual value from the source cell(s).
    
    Supports Requirement 11.1, 11.2, 11.7.
    """
    file_name: str
    sheet_name: str
    cell_range: str
    lineage_id: str
    source_value: Optional[str] = None
    
    def format(self) -> str:
        """
        Format the citation as a string.
        
        Returns:
            Formatted citation string per Requirement 11.2.
        """
        return f"[File: {self.file_name}, Sheet: {self.sheet_name}, Range: {self.cell_range}]"


class ConfidenceBreakdown(BaseModel):
    """
    Detailed confidence scores for an answer.
    
    Breaks down the overall confidence into component scores for
    file selection, sheet selection, and data retrieval.
    
    Supports Requirement 11.8.
    """
    file_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in file selection (0.0 to 1.0)"
    )
    sheet_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in sheet selection (0.0 to 1.0)"
    )
    data_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in data retrieval accuracy (0.0 to 1.0)"
    )
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score (0.0 to 1.0)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_confidence": 0.95,
                "sheet_confidence": 0.88,
                "data_confidence": 0.92,
                "overall_confidence": 0.91
            }
        }


class QueryResponse(BaseModel):
    """
    Response from the query pipeline.
    
    Contains the answer, citations, confidence scores, and metadata
    about the query processing.
    
    Supports Requirements 11.1, 11.2, 11.4, 11.5, 11.8.
    """
    answer: str = Field(
        ...,
        description="Natural language answer to the query"
    )
    citations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Source citations for factual claims in the answer"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score (0.0 to 1.0)"
    )
    confidence_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Breakdown of confidence by component (file, sheet, data)"
    )
    query_type: str = Field(
        ...,
        description="Classified query type (aggregation, lookup, summarization, comparison)"
    )
    trace_id: str = Field(
        ...,
        description="Unique identifier for query tracing and audit"
    )
    processing_time_ms: int = Field(
        ...,
        ge=0,
        description="Total processing time in milliseconds"
    )
    from_cache: bool = Field(
        default=False,
        description="Whether the response was served from cache"
    )
    disclaimer: Optional[str] = Field(
        default=None,
        description="Disclaimer when confidence is below 0.7 (Requirement 11.5)"
    )
    
    @field_validator('query_type')
    @classmethod
    def validate_query_type(cls, v: str) -> str:
        """Validate query_type is a valid QueryType value."""
        valid_types = {qt.value for qt in QueryType}
        if v not in valid_types:
            raise ValueError(f"query_type must be one of {valid_types}, got '{v}'")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "The total sales for Q1 2024 is $1,234,567",
                "citations": [
                    {
                        "file_name": "sales_2024.xlsx",
                        "sheet_name": "Q1",
                        "cell_range": "B2:B100",
                        "lineage_id": "lin_abc123"
                    }
                ],
                "confidence": 0.95,
                "confidence_breakdown": {
                    "file_confidence": 0.98,
                    "sheet_confidence": 0.94,
                    "data_confidence": 0.93
                },
                "query_type": "aggregation",
                "trace_id": "tr_abc123",
                "processing_time_ms": 450,
                "from_cache": False,
                "disclaimer": None
            }
        }


class ClarificationRequest(BaseModel):
    """
    Request for user clarification during query processing.
    
    Generated when the system needs additional information to
    process a query, such as file or sheet selection.
    
    Supports Requirements 4.3, 4.4, 5.4, 6.7.
    """
    clarification_type: str = Field(
        ...,
        description="Type of clarification needed: 'file', 'sheet', or 'query_type'"
    )
    message: str = Field(
        ...,
        description="Human-readable message explaining what clarification is needed"
    )
    options: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Available options for the user to choose from"
    )
    session_id: str = Field(
        ...,
        description="Session ID for maintaining conversation context"
    )
    pending_query: str = Field(
        ...,
        description="The original query awaiting clarification"
    )
    
    @field_validator('clarification_type')
    @classmethod
    def validate_clarification_type(cls, v: str) -> str:
        """Validate clarification_type is a valid value."""
        valid_types = {'file', 'sheet', 'query_type'}
        if v not in valid_types:
            raise ValueError(f"clarification_type must be one of {valid_types}, got '{v}'")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "clarification_type": "file",
                "message": "Multiple files match your query. Please select one:",
                "options": [
                    {
                        "file_id": "file_123",
                        "file_name": "sales_2024.xlsx",
                        "confidence": 0.75
                    },
                    {
                        "file_id": "file_456",
                        "file_name": "sales_report_2024.xlsx",
                        "confidence": 0.68
                    }
                ],
                "session_id": "sess_abc123",
                "pending_query": "What were the total sales in Q1?"
            }
        }
