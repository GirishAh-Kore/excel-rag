"""
Batch Query Processor Module.

This module implements batch query processing for executing multiple queries
in parallel with progress tracking and partial failure handling.

Key Features:
- Accept arrays of queries (max 100)
- Process queries in parallel where possible
- Return results in order with individual status
- Continue processing on partial failures
- Support progress tracking via batch_id

Supports Requirements 24.1, 24.2, 24.3, 24.4, 24.5.
"""

import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional, Protocol, Union, runtime_checkable

from src.exceptions import BatchError
from src.models.enterprise import BatchQueryRequest, BatchQueryStatus
from src.models.query_pipeline import ClarificationRequest, QueryResponse

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

MAX_BATCH_SIZE = 100
DEFAULT_MAX_WORKERS = 10
DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes for entire batch


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class BatchProcessorConfig:
    """
    Configuration for BatchQueryProcessor.
    
    Attributes:
        max_workers: Maximum parallel workers for query processing.
        timeout_seconds: Maximum time for entire batch processing.
        store_results: Whether to persist results to database.
    """
    max_workers: int = DEFAULT_MAX_WORKERS
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    store_results: bool = True
    
    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.max_workers <= 0:
            raise ValueError(f"max_workers must be positive, got {self.max_workers}")
        if self.timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {self.timeout_seconds}")


# =============================================================================
# Protocols
# =============================================================================


@runtime_checkable
class QueryExecutorProtocol(Protocol):
    """
    Protocol for query execution.
    
    Implementations must provide a method to process individual queries.
    """
    
    def process_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        file_hints: Optional[list[str]] = None,
        sheet_hints: Optional[list[str]] = None
    ) -> Union[QueryResponse, ClarificationRequest]:
        """
        Process a single query.
        
        Args:
            query: Natural language query to process.
            session_id: Optional session ID for context.
            user_id: Optional user ID for preference tracking.
            file_hints: Optional file hints to guide selection.
            sheet_hints: Optional sheet hints to guide selection.
            
        Returns:
            QueryResponse with answer or ClarificationRequest.
        """
        ...


@runtime_checkable
class BatchStoreProtocol(Protocol):
    """
    Protocol for batch status storage.
    
    Implementations must provide methods for storing and retrieving
    batch status and results.
    """
    
    def create_batch(
        self,
        batch_id: str,
        total_queries: int,
        user_id: Optional[str] = None
    ) -> bool:
        """Create a new batch record."""
        ...
    
    def update_batch_progress(
        self,
        batch_id: str,
        completed: int,
        failed: int,
        status: str
    ) -> bool:
        """Update batch progress."""
        ...
    
    def store_batch_results(
        self,
        batch_id: str,
        results: list[dict[str, Any]]
    ) -> bool:
        """Store batch results."""
        ...
    
    def get_batch_status(self, batch_id: str) -> Optional[BatchQueryStatus]:
        """Get batch status by ID."""
        ...


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class QueryResult:
    """
    Result of a single query in a batch.
    
    Attributes:
        index: Original index in the batch.
        query: The query text.
        status: 'success' or 'failed'.
        response: QueryResponse if successful.
        error: Error message if failed.
        processing_time_ms: Time taken to process.
    """
    index: int
    query: str
    status: str  # 'success' or 'failed'
    response: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    processing_time_ms: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "index": self.index,
            "query": self.query,
            "status": self.status,
            "response": self.response,
            "error": self.error,
            "processing_time_ms": self.processing_time_ms
        }


@dataclass
class BatchProgress:
    """
    Progress tracking for batch processing.
    
    Attributes:
        batch_id: Unique batch identifier.
        total_queries: Total number of queries.
        completed: Number of completed queries.
        failed: Number of failed queries.
        status: Current batch status.
        results: List of query results.
        started_at: Batch start timestamp.
    """
    batch_id: str
    total_queries: int
    completed: int = 0
    failed: int = 0
    status: str = "pending"
    results: list[QueryResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    
    def to_status(self) -> BatchQueryStatus:
        """Convert to BatchQueryStatus model."""
        return BatchQueryStatus(
            batch_id=self.batch_id,
            total_queries=self.total_queries,
            completed=self.completed,
            failed=self.failed,
            status=self.status,
            results=[r.to_dict() for r in self.results] if self.results else None
        )


# =============================================================================
# Batch Query Processor
# =============================================================================


class BatchQueryProcessor:
    """
    Processes batch queries with parallel execution and progress tracking.
    
    Coordinates the execution of multiple queries in parallel, tracking
    progress and handling partial failures gracefully. Results are returned
    in the same order as input queries.
    
    All dependencies are injected via constructor following DIP.
    
    Implements Requirements:
    - 24.1: Accept array of queries (max 100)
    - 24.2: Process queries in parallel where possible
    - 24.3: Return results in order with individual status
    - 24.4: Continue processing on partial failures
    - 24.5: Support progress tracking via batch_id
    
    Example:
        >>> processor = BatchQueryProcessor(
        ...     query_executor=orchestrator,
        ...     batch_store=store,
        ...     config=BatchProcessorConfig()
        ... )
        >>> status = processor.submit_batch(request, user_id="user_123")
        >>> # Later...
        >>> status = processor.get_batch_status(status.batch_id)
    """
    
    def __init__(
        self,
        query_executor: QueryExecutorProtocol,
        batch_store: BatchStoreProtocol,
        config: Optional[BatchProcessorConfig] = None
    ) -> None:
        """
        Initialize BatchQueryProcessor with injected dependencies.
        
        Args:
            query_executor: Service for executing individual queries.
            batch_store: Service for storing batch status and results.
            config: Optional configuration (uses defaults if not provided).
            
        Raises:
            ValueError: If any required dependency is None.
        """
        if query_executor is None:
            raise ValueError("query_executor is required")
        if batch_store is None:
            raise ValueError("batch_store is required")
        
        self._query_executor = query_executor
        self._batch_store = batch_store
        self._config = config or BatchProcessorConfig()
        
        logger.info(
            f"BatchQueryProcessor initialized with "
            f"max_workers={self._config.max_workers}"
        )
    
    def submit_batch(
        self,
        request: BatchQueryRequest,
        user_id: Optional[str] = None
    ) -> BatchQueryStatus:
        """
        Submit a batch of queries for processing.
        
        Validates the batch request, creates a batch record, and processes
        all queries in parallel. Returns the final status with results.
        
        Args:
            request: BatchQueryRequest containing queries and hints.
            user_id: Optional user ID for tracking.
            
        Returns:
            BatchQueryStatus with results when processing is complete.
            
        Raises:
            BatchError: If batch size exceeds limit or processing fails.
        """
        # Validate batch size
        if len(request.queries) > MAX_BATCH_SIZE:
            raise BatchError(
                f"Batch size {len(request.queries)} exceeds maximum of {MAX_BATCH_SIZE}",
                details={
                    "batch_size": len(request.queries),
                    "max_size": MAX_BATCH_SIZE
                }
            )
        
        # Generate batch ID
        batch_id = f"batch_{uuid.uuid4().hex[:16]}"
        
        logger.info(
            f"Starting batch {batch_id} with {len(request.queries)} queries"
        )
        
        # Create batch record
        progress = BatchProgress(
            batch_id=batch_id,
            total_queries=len(request.queries),
            status="processing"
        )
        
        if self._config.store_results:
            self._batch_store.create_batch(
                batch_id=batch_id,
                total_queries=len(request.queries),
                user_id=user_id
            )
        
        # Process queries in parallel
        try:
            results = self._process_queries_parallel(
                queries=request.queries,
                file_hints=request.file_hints,
                sheet_hints=request.sheet_hints,
                user_id=user_id,
                progress=progress
            )
            
            # Sort results by original index to maintain order
            results.sort(key=lambda r: r.index)
            progress.results = results
            
            # Determine final status
            if progress.failed == 0:
                progress.status = "completed"
            elif progress.completed == 0:
                progress.status = "failed"
            else:
                progress.status = "partial"
            
            # Store final results
            if self._config.store_results:
                self._batch_store.update_batch_progress(
                    batch_id=batch_id,
                    completed=progress.completed,
                    failed=progress.failed,
                    status=progress.status
                )
                self._batch_store.store_batch_results(
                    batch_id=batch_id,
                    results=[r.to_dict() for r in results]
                )
            
            logger.info(
                f"Batch {batch_id} completed: "
                f"{progress.completed} succeeded, {progress.failed} failed"
            )
            
            return progress.to_status()
            
        except Exception as e:
            logger.error(f"Batch {batch_id} failed: {e}", exc_info=True)
            progress.status = "failed"
            
            if self._config.store_results:
                self._batch_store.update_batch_progress(
                    batch_id=batch_id,
                    completed=progress.completed,
                    failed=progress.failed,
                    status="failed"
                )
            
            raise BatchError(
                f"Batch processing failed: {str(e)}",
                details={
                    "batch_id": batch_id,
                    "completed": progress.completed,
                    "failed": progress.failed
                }
            )
    
    def _process_queries_parallel(
        self,
        queries: list[str],
        file_hints: Optional[list[str]],
        sheet_hints: Optional[list[str]],
        user_id: Optional[str],
        progress: BatchProgress
    ) -> list[QueryResult]:
        """
        Process queries in parallel using thread pool.
        
        Args:
            queries: List of query strings.
            file_hints: Optional file hints.
            sheet_hints: Optional sheet hints.
            user_id: Optional user ID.
            progress: Progress tracker to update.
            
        Returns:
            List of QueryResult objects.
        """
        results: list[QueryResult] = []
        
        with ThreadPoolExecutor(max_workers=self._config.max_workers) as executor:
            # Submit all queries
            future_to_index = {
                executor.submit(
                    self._execute_single_query,
                    index=i,
                    query=query,
                    file_hints=file_hints,
                    sheet_hints=sheet_hints,
                    user_id=user_id
                ): i
                for i, query in enumerate(queries)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result(timeout=self._config.timeout_seconds)
                    results.append(result)
                    
                    if result.status == "success":
                        progress.completed += 1
                    else:
                        progress.failed += 1
                    
                    # Update progress in store
                    if self._config.store_results:
                        self._batch_store.update_batch_progress(
                            batch_id=progress.batch_id,
                            completed=progress.completed,
                            failed=progress.failed,
                            status="processing"
                        )
                    
                except Exception as e:
                    logger.error(f"Query {index} failed with exception: {e}")
                    results.append(QueryResult(
                        index=index,
                        query=queries[index],
                        status="failed",
                        error=str(e)
                    ))
                    progress.failed += 1
        
        return results
    
    def _execute_single_query(
        self,
        index: int,
        query: str,
        file_hints: Optional[list[str]],
        sheet_hints: Optional[list[str]],
        user_id: Optional[str]
    ) -> QueryResult:
        """
        Execute a single query and return the result.
        
        Args:
            index: Original index in the batch.
            query: Query text.
            file_hints: Optional file hints.
            sheet_hints: Optional sheet hints.
            user_id: Optional user ID.
            
        Returns:
            QueryResult with success or failure status.
        """
        start_time = time.time()
        
        try:
            response = self._query_executor.process_query(
                query=query,
                user_id=user_id,
                file_hints=file_hints,
                sheet_hints=sheet_hints
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Handle clarification requests as failures in batch mode
            if isinstance(response, ClarificationRequest):
                return QueryResult(
                    index=index,
                    query=query,
                    status="failed",
                    error=f"Query requires clarification: {response.message}",
                    processing_time_ms=processing_time_ms
                )
            
            # Convert QueryResponse to dict
            response_dict = {
                "answer": response.answer,
                "citations": response.citations,
                "confidence": response.confidence,
                "confidence_breakdown": response.confidence_breakdown,
                "query_type": response.query_type,
                "trace_id": response.trace_id,
                "processing_time_ms": response.processing_time_ms,
                "from_cache": response.from_cache,
                "disclaimer": response.disclaimer
            }
            
            return QueryResult(
                index=index,
                query=query,
                status="success",
                response=response_dict,
                processing_time_ms=processing_time_ms
            )
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"Query {index} failed: {e}")
            
            return QueryResult(
                index=index,
                query=query,
                status="failed",
                error=str(e),
                processing_time_ms=processing_time_ms
            )
    
    def get_batch_status(self, batch_id: str) -> Optional[BatchQueryStatus]:
        """
        Get the current status of a batch.
        
        Args:
            batch_id: Unique batch identifier.
            
        Returns:
            BatchQueryStatus if found, None otherwise.
        """
        return self._batch_store.get_batch_status(batch_id)
