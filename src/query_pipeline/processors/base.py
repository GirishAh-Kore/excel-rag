"""
Base Query Processor Module.

This module defines the abstract base class for all query processors and
the common data structures used across processors.

Key Components:
- BaseQueryProcessor: Abstract base class defining the processor interface
- ProcessedResult: Result of query processing
- RetrievedData: Data retrieved from vector store for processing
- ProcessorConfig: Configuration for processors

Supports Requirements 7.1, 8.1, 9.1, 10.1.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from src.models.query_pipeline import QueryClassification, QueryType


@dataclass
class ProcessorConfig:
    """
    Configuration for query processors.
    
    Attributes:
        max_rows: Maximum rows to process (default 100000).
        max_results: Maximum results to return for lookups (default 10).
        sampling_threshold: Row count above which sampling is used (default 1000).
        sample_size: Number of rows to sample for large datasets (default 100).
        max_summary_words: Maximum words in summaries (default 500).
        numeric_precision: Decimal places for numeric results (default 6).
        timeout_seconds: Processing timeout in seconds (default 30).
    """
    max_rows: int = 100000
    max_results: int = 10
    sampling_threshold: int = 1000
    sample_size: int = 100
    max_summary_words: int = 500
    numeric_precision: int = 6
    timeout_seconds: int = 30
    
    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.max_rows <= 0:
            raise ValueError(f"max_rows must be positive, got {self.max_rows}")
        if self.max_results <= 0:
            raise ValueError(f"max_results must be positive, got {self.max_results}")
        if self.sampling_threshold <= 0:
            raise ValueError(
                f"sampling_threshold must be positive, got {self.sampling_threshold}"
            )
        if self.sample_size <= 0:
            raise ValueError(f"sample_size must be positive, got {self.sample_size}")
        if self.max_summary_words <= 0:
            raise ValueError(
                f"max_summary_words must be positive, got {self.max_summary_words}"
            )


@dataclass
class RetrievedData:
    """
    Data retrieved from vector store for query processing.
    
    Contains the raw data, metadata, and context needed for processing.
    
    Attributes:
        file_id: ID of the source file.
        file_name: Name of the source file.
        sheet_name: Name of the source sheet.
        headers: Column headers from the data.
        rows: List of row data (each row is a dict mapping header to value).
        cell_range: Cell range of the data (e.g., "A1:D100").
        chunk_ids: IDs of chunks this data came from.
        total_rows: Total rows in the source (may be more than rows if sampled).
        is_sampled: Whether the data was sampled from a larger dataset.
        metadata: Additional metadata about the data.
    """
    file_id: str
    file_name: str
    sheet_name: str
    headers: list[str]
    rows: list[dict[str, Any]]
    cell_range: str
    chunk_ids: list[str] = field(default_factory=list)
    total_rows: int = 0
    is_sampled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Set total_rows if not provided."""
        if self.total_rows == 0:
            self.total_rows = len(self.rows)
    
    @property
    def row_count(self) -> int:
        """Get the number of rows in the retrieved data."""
        return len(self.rows)
    
    @property
    def column_count(self) -> int:
        """Get the number of columns in the retrieved data."""
        return len(self.headers)


@dataclass
class ProcessedResult:
    """
    Result of query processing.
    
    Contains the computed result, source information for citations,
    and processing metadata.
    
    Attributes:
        success: Whether processing succeeded.
        result_type: Type of result (value, rows, summary, comparison).
        value: Computed value for aggregations.
        rows: Result rows for lookups.
        summary: Generated summary text.
        comparison: Comparison result data.
        source_file: Source file name.
        source_sheet: Source sheet name.
        source_range: Source cell range.
        chunk_ids: IDs of chunks used.
        rows_processed: Number of rows processed.
        rows_skipped: Number of rows skipped (e.g., non-numeric).
        warnings: Processing warnings.
        error_message: Error message if success is False.
        metadata: Additional result metadata.
    """
    success: bool
    result_type: str  # "value", "rows", "summary", "comparison"
    value: Optional[Any] = None
    rows: Optional[list[dict[str, Any]]] = None
    summary: Optional[str] = None
    comparison: Optional[dict[str, Any]] = None
    source_file: str = ""
    source_sheet: str = ""
    source_range: str = ""
    chunk_ids: list[str] = field(default_factory=list)
    rows_processed: int = 0
    rows_skipped: int = 0
    warnings: list[str] = field(default_factory=list)
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def error(cls, message: str, **kwargs: Any) -> "ProcessedResult":
        """
        Create an error result.
        
        Args:
            message: Error message.
            **kwargs: Additional fields to set.
            
        Returns:
            ProcessedResult with success=False.
        """
        return cls(
            success=False,
            result_type="error",
            error_message=message,
            **kwargs
        )
    
    @classmethod
    def aggregation(
        cls,
        value: Any,
        source_file: str,
        source_sheet: str,
        source_range: str,
        rows_processed: int,
        rows_skipped: int = 0,
        warnings: Optional[list[str]] = None,
        chunk_ids: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None
    ) -> "ProcessedResult":
        """
        Create an aggregation result.
        
        Args:
            value: Computed aggregation value.
            source_file: Source file name.
            source_sheet: Source sheet name.
            source_range: Source cell range.
            rows_processed: Number of rows processed.
            rows_skipped: Number of rows skipped.
            warnings: Processing warnings.
            chunk_ids: IDs of chunks used.
            metadata: Additional metadata.
            
        Returns:
            ProcessedResult for aggregation.
        """
        return cls(
            success=True,
            result_type="value",
            value=value,
            source_file=source_file,
            source_sheet=source_sheet,
            source_range=source_range,
            rows_processed=rows_processed,
            rows_skipped=rows_skipped,
            warnings=warnings or [],
            chunk_ids=chunk_ids or [],
            metadata=metadata or {}
        )
    
    @classmethod
    def lookup(
        cls,
        rows: list[dict[str, Any]],
        source_file: str,
        source_sheet: str,
        source_range: str,
        total_matches: int,
        warnings: Optional[list[str]] = None,
        chunk_ids: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None
    ) -> "ProcessedResult":
        """
        Create a lookup result.
        
        Args:
            rows: Matching rows.
            source_file: Source file name.
            source_sheet: Source sheet name.
            source_range: Source cell range.
            total_matches: Total number of matches (may exceed returned rows).
            warnings: Processing warnings.
            chunk_ids: IDs of chunks used.
            metadata: Additional metadata.
            
        Returns:
            ProcessedResult for lookup.
        """
        return cls(
            success=True,
            result_type="rows",
            rows=rows,
            source_file=source_file,
            source_sheet=source_sheet,
            source_range=source_range,
            rows_processed=total_matches,
            warnings=warnings or [],
            chunk_ids=chunk_ids or [],
            metadata=metadata or {"total_matches": total_matches}
        )


class BaseQueryProcessor(ABC):
    """
    Abstract base class for all query processors.
    
    Defines the interface that all query processors must implement.
    Processors are responsible for executing specific query types
    (aggregation, lookup, summarization, comparison) on retrieved data.
    
    Subclasses must implement:
    - process(): Execute the query and return results
    - can_process(): Check if this processor can handle a classification
    
    Supports Requirements 7.1, 8.1, 9.1, 10.1.
    
    Example:
        >>> class MyProcessor(BaseQueryProcessor):
        ...     def can_process(self, classification):
        ...         return classification.query_type == QueryType.AGGREGATION
        ...
        ...     def process(self, query, data, classification):
        ...         # Process the query
        ...         return ProcessedResult.aggregation(...)
    """
    
    def __init__(self, config: Optional[ProcessorConfig] = None) -> None:
        """
        Initialize the processor with configuration.
        
        Args:
            config: Optional processor configuration. Uses defaults if not provided.
        """
        self._config = config or ProcessorConfig()
    
    @property
    def config(self) -> ProcessorConfig:
        """Get the processor configuration."""
        return self._config
    
    @abstractmethod
    def can_process(self, classification: QueryClassification) -> bool:
        """
        Check if this processor can handle the given classification.
        
        Args:
            classification: The query classification to check.
            
        Returns:
            True if this processor can handle the query, False otherwise.
        """
        ...
    
    @abstractmethod
    def process(
        self,
        query: str,
        data: RetrievedData,
        classification: QueryClassification
    ) -> ProcessedResult:
        """
        Process the query and return results.
        
        Args:
            query: The original query text.
            data: Retrieved data to process.
            classification: Query classification with extracted parameters.
            
        Returns:
            ProcessedResult containing the query results.
            
        Raises:
            ProcessingError: If processing fails.
        """
        ...
    
    def get_supported_query_type(self) -> QueryType:
        """
        Get the query type this processor supports.
        
        Subclasses should override this to return their supported type.
        
        Returns:
            The QueryType this processor handles.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_supported_query_type()"
        )
