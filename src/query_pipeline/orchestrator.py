"""
Query Pipeline Orchestrator Module.

This module implements the central orchestrator for the smart Excel query pipeline.
It coordinates file selection, sheet selection, query classification, processing,
and answer generation with full traceability and session-based context support.

Key Features:
- Full pipeline coordination from query to answer
- Session-based context for multi-turn conversations
- Clarification handling for ambiguous queries
- Timeout handling with configurable limits
- Complete traceability via TraceRecorder

Supports Requirements 4.1, 5.1, 6.1, 7.1, 11.1, 12.1-12.6, 14.6.
"""

import asyncio
import hashlib
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Optional, Protocol, Union, runtime_checkable

from src.abstractions.cache_service import CacheService
from src.abstractions.vector_store import VectorStore
from src.exceptions import (
    ProcessingError,
    QueryError,
    SelectionError,
)
from src.models.query_pipeline import (
    ClarificationRequest,
    QueryClassification,
    QueryResponse,
    QueryType,
)
from src.query_pipeline.answer_generator import AnswerGenerator
from src.query_pipeline.classifier import QueryClassifier
from src.query_pipeline.file_selector import (
    FileSelectionResult,
    FileSelector,
    SelectionAction as FileSelectionAction,
)
from src.query_pipeline.processor_registry import QueryProcessorRegistry
from src.query_pipeline.processors.base import ProcessedResult, RetrievedData
from src.query_pipeline.sheet_selector import (
    CombinationStrategy,
    SelectionAction as SheetSelectionAction,
    SheetSelectionResult,
    SheetSelector,
)
from src.traceability.trace_recorder import TraceRecorder

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class QueryPipelineConfig:
    """
    Configuration for QueryPipelineOrchestrator.
    
    Attributes:
        timeout_seconds: Maximum time for query processing (default 30).
        max_chunks_per_query: Maximum chunks to retrieve per query (default 20).
        session_ttl_seconds: Session context TTL in seconds (default 3600).
        enable_caching: Whether to cache query results (default True).
        cache_ttl_seconds: Cache TTL for query results (default 3600).
        similarity_threshold: Minimum similarity for name suggestions (default 0.6).
        max_suggestions: Maximum similar name suggestions (default 3).
    """
    timeout_seconds: int = 30
    max_chunks_per_query: int = 20
    session_ttl_seconds: int = 3600
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    similarity_threshold: float = 0.6
    max_suggestions: int = 3
    
    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {self.timeout_seconds}")
        if self.max_chunks_per_query <= 0:
            raise ValueError(
                f"max_chunks_per_query must be positive, got {self.max_chunks_per_query}"
            )
        if self.session_ttl_seconds <= 0:
            raise ValueError(
                f"session_ttl_seconds must be positive, got {self.session_ttl_seconds}"
            )
        if not 0.0 <= self.similarity_threshold <= 1.0:
            raise ValueError(
                f"similarity_threshold must be 0-1, got {self.similarity_threshold}"
            )


# =============================================================================
# Protocols for Dependencies
# =============================================================================


@runtime_checkable
class DataRetrieverProtocol(Protocol):
    """
    Protocol for data retrieval from vector store.
    
    Implementations must provide methods for retrieving chunk data
    based on file and sheet selection.
    """
    
    def retrieve_data(
        self,
        file_id: str,
        sheet_names: list[str],
        query: str,
        max_chunks: int = 20
    ) -> RetrievedData:
        """
        Retrieve data from vector store for query processing.
        
        Args:
            file_id: ID of the file to retrieve from.
            sheet_names: Names of sheets to retrieve from.
            query: Query for semantic search.
            max_chunks: Maximum chunks to retrieve.
            
        Returns:
            RetrievedData containing the retrieved chunks.
        """
        ...


@runtime_checkable  
class SessionStoreProtocol(Protocol):
    """
    Protocol for session context storage.
    
    Implementations must provide methods for storing and retrieving
    session context for multi-turn conversations.
    """
    
    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Get session context by ID."""
        ...
    
    def set_session(
        self,
        session_id: str,
        context: dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Store session context."""
        ...
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session context."""
        ...


# =============================================================================
# Session Context
# =============================================================================


@dataclass
class SessionContext:
    """
    Context for multi-turn conversation sessions.
    
    Stores pending queries, selected files/sheets, and clarification state.
    
    Attributes:
        session_id: Unique session identifier.
        pending_query: Query awaiting clarification.
        pending_clarification_type: Type of clarification needed.
        selected_file_id: Previously selected file ID.
        selected_file_name: Previously selected file name.
        selected_sheets: Previously selected sheet names.
        file_selection_result: Cached file selection result.
        sheet_selection_result: Cached sheet selection result.
        classification: Cached query classification.
        trace_id: Current trace ID.
        created_at: Session creation timestamp.
    """
    session_id: str
    pending_query: Optional[str] = None
    pending_clarification_type: Optional[str] = None
    selected_file_id: Optional[str] = None
    selected_file_name: Optional[str] = None
    selected_sheets: list[str] = field(default_factory=list)
    file_selection_result: Optional[FileSelectionResult] = None
    sheet_selection_result: Optional[SheetSelectionResult] = None
    classification: Optional[QueryClassification] = None
    trace_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "session_id": self.session_id,
            "pending_query": self.pending_query,
            "pending_clarification_type": self.pending_clarification_type,
            "selected_file_id": self.selected_file_id,
            "selected_file_name": self.selected_file_name,
            "selected_sheets": self.selected_sheets,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionContext":
        """Create from dictionary."""
        return cls(
            session_id=data.get("session_id", ""),
            pending_query=data.get("pending_query"),
            pending_clarification_type=data.get("pending_clarification_type"),
            selected_file_id=data.get("selected_file_id"),
            selected_file_name=data.get("selected_file_name"),
            selected_sheets=data.get("selected_sheets", []),
            trace_id=data.get("trace_id"),
            created_at=data.get("created_at", time.time()),
        )


# =============================================================================
# Query Pipeline Orchestrator
# =============================================================================


class QueryPipelineOrchestrator:
    """
    Central orchestrator for the smart Excel query pipeline.
    
    Coordinates file selection, sheet selection, query classification,
    processing, and answer generation with full traceability. Supports
    session-based context for multi-turn conversations and handles
    clarification requests when selections are ambiguous.
    
    All dependencies are injected via constructor following DIP.
    
    Implements Requirements:
    - 4.1: Smart file selection with weighted scoring
    - 5.1: Smart sheet selection with weighted scoring
    - 6.1: Query classification into types
    - 7.1, 8.1, 9.1, 10.1: Query processing by type
    - 11.1: Answer generation with citations
    - 12.1-12.6: Error handling with user-friendly messages
    - 14.6: Session-based context for multi-turn conversations
    
    Example:
        >>> orchestrator = QueryPipelineOrchestrator(
        ...     file_selector=file_sel,
        ...     sheet_selector=sheet_sel,
        ...     query_classifier=classifier,
        ...     answer_generator=answer_gen,
        ...     trace_recorder=trace_rec,
        ...     data_retriever=retriever,
        ...     session_store=session_store,
        ...     cache_service=cache_svc,
        ...     config=QueryPipelineConfig()
        ... )
        >>> response = orchestrator.process_query("What is the total sales?")
    """
    
    def __init__(
        self,
        file_selector: FileSelector,
        sheet_selector: SheetSelector,
        query_classifier: QueryClassifier,
        answer_generator: AnswerGenerator,
        trace_recorder: TraceRecorder,
        data_retriever: DataRetrieverProtocol,
        session_store: SessionStoreProtocol,
        cache_service: CacheService,
        config: Optional[QueryPipelineConfig] = None
    ) -> None:
        """
        Initialize QueryPipelineOrchestrator with injected dependencies.
        
        Args:
            file_selector: Service for ranking and selecting files.
            sheet_selector: Service for ranking and selecting sheets.
            query_classifier: Service for classifying query types.
            answer_generator: Service for generating answers with citations.
            trace_recorder: Service for recording query traces.
            data_retriever: Service for retrieving data from vector store.
            session_store: Service for storing session context.
            cache_service: Service for caching query results.
            config: Optional configuration (uses defaults if not provided).
            
        Raises:
            ValueError: If any required dependency is None.
        """
        if file_selector is None:
            raise ValueError("file_selector is required")
        if sheet_selector is None:
            raise ValueError("sheet_selector is required")
        if query_classifier is None:
            raise ValueError("query_classifier is required")
        if answer_generator is None:
            raise ValueError("answer_generator is required")
        if trace_recorder is None:
            raise ValueError("trace_recorder is required")
        if data_retriever is None:
            raise ValueError("data_retriever is required")
        if session_store is None:
            raise ValueError("session_store is required")
        if cache_service is None:
            raise ValueError("cache_service is required")
        
        self._file_selector = file_selector
        self._sheet_selector = sheet_selector
        self._query_classifier = query_classifier
        self._answer_generator = answer_generator
        self._trace_recorder = trace_recorder
        self._data_retriever = data_retriever
        self._session_store = session_store
        self._cache_service = cache_service
        self._config = config or QueryPipelineConfig()
        
        # Thread pool for timeout handling
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info(
            f"QueryPipelineOrchestrator initialized with "
            f"timeout={self._config.timeout_seconds}s"
        )


    def process_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        file_hints: Optional[list[str]] = None,
        sheet_hints: Optional[list[str]] = None
    ) -> Union[QueryResponse, ClarificationRequest]:
        """
        Process a natural language query through the full pipeline.
        
        Coordinates file selection, sheet selection, classification,
        processing, and answer generation. Returns either a QueryResponse
        with the answer or a ClarificationRequest if user input is needed.
        
        Args:
            query: Natural language query to process.
            session_id: Optional session ID for multi-turn context.
            user_id: Optional user ID for preference tracking.
            file_hints: Optional file name hints to guide selection.
            sheet_hints: Optional sheet name hints to guide selection.
            
        Returns:
            QueryResponse with answer and citations, or
            ClarificationRequest if clarification is needed.
            
        Raises:
            QueryError: If query processing fails.
            ProcessingError: If data processing fails.
        """
        start_time = time.time()
        
        if not query or not query.strip():
            raise QueryError(
                "Query cannot be empty",
                details={"query": query}
            )
        
        query = query.strip()
        logger.info(f"Processing query: {query[:100]}...")
        
        # Generate or retrieve session
        if session_id is None:
            session_id = f"sess_{uuid.uuid4().hex[:16]}"
        
        session = self._get_or_create_session(session_id)
        
        # Check cache if enabled
        if self._config.enable_caching:
            cached_response = self._check_cache(query, file_hints, sheet_hints)
            if cached_response:
                logger.info("Returning cached response")
                return cached_response
        
        # Start trace
        trace_id = self._trace_recorder.start_trace(
            query=query,
            user_id=user_id,
            session_id=session_id
        )
        session.trace_id = trace_id
        
        try:
            # Execute pipeline with timeout
            result = self._execute_with_timeout(
                self._execute_pipeline,
                query=query,
                session=session,
                user_id=user_id,
                file_hints=file_hints,
                sheet_hints=sheet_hints,
                start_time=start_time
            )
            
            # Cache successful responses
            if isinstance(result, QueryResponse) and self._config.enable_caching:
                self._cache_response(query, file_hints, sheet_hints, result)
            
            return result
            
        except FuturesTimeoutError:
            self._trace_recorder.abort_trace(trace_id)
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            logger.error(f"Query processing timed out after {self._config.timeout_seconds}s")
            raise QueryError(
                f"Query processing timed out after {self._config.timeout_seconds} seconds. "
                "Please try a simpler query or contact support.",
                details={
                    "query": query[:100],
                    "timeout_seconds": self._config.timeout_seconds,
                    "processing_time_ms": processing_time_ms,
                    "trace_id": trace_id
                }
            )
        except (QueryError, ProcessingError, SelectionError):
            self._trace_recorder.abort_trace(trace_id)
            raise
        except Exception as e:
            self._trace_recorder.abort_trace(trace_id)
            logger.error(f"Unexpected error in query processing: {e}", exc_info=True)
            raise QueryError(
                f"An unexpected error occurred while processing your query. "
                f"Please try again or contact support. (Error ID: {trace_id})",
                details={
                    "query": query[:100],
                    "error": str(e),
                    "trace_id": trace_id
                }
            )

    def _execute_pipeline(
        self,
        query: str,
        session: SessionContext,
        user_id: Optional[str],
        file_hints: Optional[list[str]],
        sheet_hints: Optional[list[str]],
        start_time: float
    ) -> Union[QueryResponse, ClarificationRequest]:
        """
        Execute the full query pipeline.
        
        Args:
            query: Query text.
            session: Session context.
            user_id: Optional user ID.
            file_hints: Optional file hints.
            sheet_hints: Optional sheet hints.
            start_time: Pipeline start time.
            
        Returns:
            QueryResponse or ClarificationRequest.
        """
        trace_id = session.trace_id or ""
        
        # Step 1: File Selection
        file_selection_start = time.time()
        file_result = self._select_file(query, user_id, file_hints)
        file_selection_time_ms = int((time.time() - file_selection_start) * 1000)
        
        # Handle file selection clarification
        if file_result.action == FileSelectionAction.CLARIFY:
            return self._create_file_clarification(
                file_result=file_result,
                session=session,
                query=query
            )
        
        if file_result.action == FileSelectionAction.LOW_CONFIDENCE:
            return self._create_file_clarification(
                file_result=file_result,
                session=session,
                query=query,
                low_confidence=True
            )
        
        # File auto-selected
        selected_file = file_result.selected_file
        if selected_file is None:
            raise SelectionError(
                "No file could be selected for your query.",
                details={"query": query[:100], "trace_id": trace_id}
            )
        
        # Record file selection in trace
        self._trace_recorder.record_file_selection(
            trace_id=trace_id,
            candidates=file_result.candidates,
            selected_file_id=selected_file.file_id,
            reasoning=file_result.message,
            confidence=file_result.top_confidence,
            time_ms=file_selection_time_ms
        )
        
        # Update session
        session.selected_file_id = selected_file.file_id
        session.selected_file_name = selected_file.file_name
        session.file_selection_result = file_result
        
        # Step 2: Sheet Selection
        sheet_selection_start = time.time()
        sheet_result = self._select_sheets(
            file_id=selected_file.file_id,
            query=query,
            sheet_hints=sheet_hints
        )
        sheet_selection_time_ms = int((time.time() - sheet_selection_start) * 1000)
        
        # Handle sheet selection clarification
        if sheet_result.action == SheetSelectionAction.CLARIFY:
            return self._create_sheet_clarification(
                sheet_result=sheet_result,
                session=session,
                query=query
            )
        
        # Get selected sheet names
        selected_sheets = [s.sheet_name for s in sheet_result.selected_sheets]
        if not selected_sheets:
            raise SelectionError(
                f"No sheets could be selected from file '{selected_file.file_name}'.",
                details={
                    "file_id": selected_file.file_id,
                    "query": query[:100],
                    "trace_id": trace_id
                }
            )
        
        # Record sheet selection in trace
        self._trace_recorder.record_sheet_selection(
            trace_id=trace_id,
            candidates=sheet_result.candidates,
            selected_sheets=selected_sheets,
            reasoning=sheet_result.message,
            confidence=sheet_result.top_confidence,
            time_ms=sheet_selection_time_ms
        )
        
        # Update session
        session.selected_sheets = selected_sheets
        session.sheet_selection_result = sheet_result
        
        # Step 3: Query Classification
        classification = self._query_classifier.classify(query)
        
        # Record classification in trace
        self._trace_recorder.record_classification(
            trace_id=trace_id,
            query_type=classification.query_type,
            confidence=classification.confidence
        )
        
        session.classification = classification
        
        # Step 4: Data Retrieval
        retrieval_start = time.time()
        retrieved_data = self._data_retriever.retrieve_data(
            file_id=selected_file.file_id,
            sheet_names=selected_sheets,
            query=query,
            max_chunks=self._config.max_chunks_per_query
        )
        retrieval_time_ms = int((time.time() - retrieval_start) * 1000)
        
        # Record retrieval in trace
        self._trace_recorder.record_retrieval(
            trace_id=trace_id,
            chunk_ids=retrieved_data.chunk_ids,
            scores=[],  # Scores would come from vector search
            time_ms=retrieval_time_ms
        )
        
        # Step 5: Query Processing
        processor = QueryProcessorRegistry.get_processor(classification.query_type)
        processed_result = processor.process(
            query=query,
            data=retrieved_data,
            classification=classification
        )
        
        # Step 6: Answer Generation
        generation_start = time.time()
        response = self._answer_generator.generate(
            query=query,
            processed_result=processed_result,
            query_type=classification.query_type,
            file_confidence=file_result.top_confidence,
            sheet_confidence=sheet_result.top_confidence,
            trace_id=trace_id,
            processing_time_ms=int((time.time() - start_time) * 1000),
            from_cache=False
        )
        generation_time_ms = int((time.time() - generation_start) * 1000)
        
        # Complete trace
        self._trace_recorder.complete_trace(
            trace_id=trace_id,
            answer=response.answer,
            citations=[],  # Citations are in response
            confidence=response.confidence,
            generation_time_ms=generation_time_ms
        )
        
        # Record user selection for preference learning
        self._file_selector.record_user_selection(
            query=query,
            file_id=selected_file.file_id,
            user_id=user_id
        )
        
        # Save session
        self._save_session(session)
        
        return response


    def handle_clarification(
        self,
        session_id: str,
        clarification_type: str,
        selected_value: str
    ) -> Union[QueryResponse, ClarificationRequest]:
        """
        Handle user response to a clarification request.
        
        Continues query processing with the user's selection.
        
        Args:
            session_id: Session ID from the clarification request.
            clarification_type: Type of clarification ('file', 'sheet', 'query_type').
            selected_value: User's selected value (file_id, sheet_name, or query_type).
            
        Returns:
            QueryResponse with answer, or another ClarificationRequest if needed.
            
        Raises:
            QueryError: If session not found or clarification handling fails.
        """
        logger.info(
            f"Handling clarification: session={session_id}, "
            f"type={clarification_type}, value={selected_value}"
        )
        
        # Retrieve session
        session = self._get_session(session_id)
        if session is None:
            raise QueryError(
                "Session not found or expired. Please submit your query again.",
                details={"session_id": session_id}
            )
        
        if session.pending_query is None:
            raise QueryError(
                "No pending query found for this session.",
                details={"session_id": session_id}
            )
        
        query = session.pending_query
        trace_id = session.trace_id
        start_time = time.time()
        
        try:
            if clarification_type == "file":
                return self._handle_file_clarification(
                    session=session,
                    selected_file_id=selected_value,
                    start_time=start_time
                )
            elif clarification_type == "sheet":
                return self._handle_sheet_clarification(
                    session=session,
                    selected_sheet_name=selected_value,
                    start_time=start_time
                )
            elif clarification_type == "query_type":
                return self._handle_query_type_clarification(
                    session=session,
                    selected_query_type=selected_value,
                    start_time=start_time
                )
            else:
                raise QueryError(
                    f"Unknown clarification type: {clarification_type}",
                    details={
                        "clarification_type": clarification_type,
                        "valid_types": ["file", "sheet", "query_type"]
                    }
                )
        except (QueryError, ProcessingError, SelectionError):
            if trace_id:
                self._trace_recorder.abort_trace(trace_id)
            raise
        except Exception as e:
            if trace_id:
                self._trace_recorder.abort_trace(trace_id)
            logger.error(f"Error handling clarification: {e}", exc_info=True)
            raise QueryError(
                f"Failed to process your selection. Please try again. "
                f"(Error ID: {trace_id})",
                details={"error": str(e), "trace_id": trace_id}
            )

    def _handle_file_clarification(
        self,
        session: SessionContext,
        selected_file_id: str,
        start_time: float
    ) -> Union[QueryResponse, ClarificationRequest]:
        """Handle file selection clarification response."""
        query = session.pending_query or ""
        trace_id = session.trace_id or ""
        
        # Validate selection against candidates
        file_result = session.file_selection_result
        if file_result is None:
            raise QueryError(
                "File selection context not found. Please submit your query again.",
                details={"session_id": session.session_id}
            )
        
        selected_candidate = None
        for candidate in file_result.candidates:
            if candidate.file_id == selected_file_id:
                selected_candidate = candidate
                break
        
        if selected_candidate is None:
            # Try to find similar file names and suggest
            suggestions = self._find_similar_names(
                selected_file_id,
                [c.file_name for c in file_result.candidates]
            )
            suggestion_text = ""
            if suggestions:
                suggestion_text = f" Did you mean: {', '.join(suggestions)}?"
            
            raise SelectionError(
                f"File '{selected_file_id}' not found in available options.{suggestion_text}",
                details={
                    "selected_file_id": selected_file_id,
                    "available_files": [c.file_id for c in file_result.candidates],
                    "suggestions": suggestions
                }
            )
        
        # Record file selection in trace
        self._trace_recorder.record_file_selection(
            trace_id=trace_id,
            candidates=file_result.candidates,
            selected_file_id=selected_file_id,
            reasoning=f"User selected file: {selected_candidate.file_name}",
            confidence=selected_candidate.combined_score,
            time_ms=0
        )
        
        # Update session
        session.selected_file_id = selected_file_id
        session.selected_file_name = selected_candidate.file_name
        session.pending_clarification_type = None
        
        # Continue with sheet selection
        return self._continue_from_file_selection(
            session=session,
            selected_file=selected_candidate,
            start_time=start_time
        )

    def _handle_sheet_clarification(
        self,
        session: SessionContext,
        selected_sheet_name: str,
        start_time: float
    ) -> Union[QueryResponse, ClarificationRequest]:
        """Handle sheet selection clarification response."""
        query = session.pending_query or ""
        trace_id = session.trace_id or ""
        
        # Validate selection against candidates
        sheet_result = session.sheet_selection_result
        if sheet_result is None:
            raise QueryError(
                "Sheet selection context not found. Please submit your query again.",
                details={"session_id": session.session_id}
            )
        
        selected_candidate = None
        for candidate in sheet_result.candidates:
            if candidate.sheet_name == selected_sheet_name:
                selected_candidate = candidate
                break
        
        if selected_candidate is None:
            # Try to find similar sheet names and suggest
            suggestions = self._find_similar_names(
                selected_sheet_name,
                [c.sheet_name for c in sheet_result.candidates]
            )
            suggestion_text = ""
            if suggestions:
                suggestion_text = f" Did you mean: {', '.join(suggestions)}?"
            
            raise SelectionError(
                f"Sheet '{selected_sheet_name}' not found in available options.{suggestion_text}",
                details={
                    "selected_sheet_name": selected_sheet_name,
                    "available_sheets": [c.sheet_name for c in sheet_result.candidates],
                    "suggestions": suggestions
                }
            )
        
        # Record sheet selection in trace
        self._trace_recorder.record_sheet_selection(
            trace_id=trace_id,
            candidates=sheet_result.candidates,
            selected_sheets=[selected_sheet_name],
            reasoning=f"User selected sheet: {selected_sheet_name}",
            confidence=selected_candidate.combined_score,
            time_ms=0
        )
        
        # Update session
        session.selected_sheets = [selected_sheet_name]
        session.pending_clarification_type = None
        
        # Continue with query processing
        return self._continue_from_sheet_selection(
            session=session,
            selected_sheets=[selected_candidate],
            start_time=start_time
        )

    def _handle_query_type_clarification(
        self,
        session: SessionContext,
        selected_query_type: str,
        start_time: float
    ) -> Union[QueryResponse, ClarificationRequest]:
        """Handle query type clarification response."""
        query = session.pending_query or ""
        trace_id = session.trace_id or ""
        
        # Validate query type
        try:
            query_type = QueryType(selected_query_type)
        except ValueError:
            valid_types = [qt.value for qt in QueryType]
            raise QueryError(
                f"Invalid query type: {selected_query_type}. "
                f"Valid types are: {', '.join(valid_types)}",
                details={
                    "selected_query_type": selected_query_type,
                    "valid_types": valid_types
                }
            )
        
        # Get existing classification and update
        classification = session.classification
        if classification is None:
            classification = self._query_classifier.classify(query)
        
        # Override with user selection
        classification = QueryClassification(
            query_type=query_type,
            confidence=1.0,  # User explicitly selected
            alternative_types=[],
            detected_aggregations=classification.detected_aggregations,
            detected_filters=classification.detected_filters,
            detected_columns=classification.detected_columns
        )
        
        # Record classification in trace
        self._trace_recorder.record_classification(
            trace_id=trace_id,
            query_type=query_type,
            confidence=1.0
        )
        
        session.classification = classification
        session.pending_clarification_type = None
        
        # Continue with data retrieval and processing
        return self._continue_from_classification(
            session=session,
            classification=classification,
            start_time=start_time
        )


    # =========================================================================
    # Continuation Methods
    # =========================================================================

    def _continue_from_file_selection(
        self,
        session: SessionContext,
        selected_file: Any,
        start_time: float
    ) -> Union[QueryResponse, ClarificationRequest]:
        """Continue pipeline from after file selection."""
        query = session.pending_query or ""
        trace_id = session.trace_id or ""
        
        # Sheet Selection
        sheet_selection_start = time.time()
        sheet_result = self._select_sheets(
            file_id=selected_file.file_id,
            query=query,
            sheet_hints=None
        )
        sheet_selection_time_ms = int((time.time() - sheet_selection_start) * 1000)
        
        # Handle sheet selection clarification
        if sheet_result.action == SheetSelectionAction.CLARIFY:
            return self._create_sheet_clarification(
                sheet_result=sheet_result,
                session=session,
                query=query
            )
        
        selected_sheets = [s.sheet_name for s in sheet_result.selected_sheets]
        if not selected_sheets:
            raise SelectionError(
                f"No sheets could be selected from file '{selected_file.file_name}'.",
                details={"file_id": selected_file.file_id, "trace_id": trace_id}
            )
        
        # Record sheet selection
        self._trace_recorder.record_sheet_selection(
            trace_id=trace_id,
            candidates=sheet_result.candidates,
            selected_sheets=selected_sheets,
            reasoning=sheet_result.message,
            confidence=sheet_result.top_confidence,
            time_ms=sheet_selection_time_ms
        )
        
        session.selected_sheets = selected_sheets
        session.sheet_selection_result = sheet_result
        
        # Continue with classification and processing
        return self._continue_from_sheet_selection(
            session=session,
            selected_sheets=sheet_result.selected_sheets,
            start_time=start_time
        )

    def _continue_from_sheet_selection(
        self,
        session: SessionContext,
        selected_sheets: list[Any],
        start_time: float
    ) -> Union[QueryResponse, ClarificationRequest]:
        """Continue pipeline from after sheet selection."""
        query = session.pending_query or ""
        trace_id = session.trace_id or ""
        
        # Classification
        classification = self._query_classifier.classify(query)
        
        self._trace_recorder.record_classification(
            trace_id=trace_id,
            query_type=classification.query_type,
            confidence=classification.confidence
        )
        
        session.classification = classification
        
        # Continue with data retrieval and processing
        return self._continue_from_classification(
            session=session,
            classification=classification,
            start_time=start_time
        )

    def _continue_from_classification(
        self,
        session: SessionContext,
        classification: QueryClassification,
        start_time: float
    ) -> QueryResponse:
        """Continue pipeline from after classification."""
        query = session.pending_query or ""
        trace_id = session.trace_id or ""
        file_id = session.selected_file_id or ""
        sheet_names = session.selected_sheets
        
        # Get confidence scores from cached results
        file_confidence = 1.0
        sheet_confidence = 1.0
        if session.file_selection_result:
            file_confidence = session.file_selection_result.top_confidence
        if session.sheet_selection_result:
            sheet_confidence = session.sheet_selection_result.top_confidence
        
        # Data Retrieval
        retrieval_start = time.time()
        retrieved_data = self._data_retriever.retrieve_data(
            file_id=file_id,
            sheet_names=sheet_names,
            query=query,
            max_chunks=self._config.max_chunks_per_query
        )
        retrieval_time_ms = int((time.time() - retrieval_start) * 1000)
        
        self._trace_recorder.record_retrieval(
            trace_id=trace_id,
            chunk_ids=retrieved_data.chunk_ids,
            scores=[],
            time_ms=retrieval_time_ms
        )
        
        # Query Processing
        processor = QueryProcessorRegistry.get_processor(classification.query_type)
        processed_result = processor.process(
            query=query,
            data=retrieved_data,
            classification=classification
        )
        
        # Answer Generation
        generation_start = time.time()
        response = self._answer_generator.generate(
            query=query,
            processed_result=processed_result,
            query_type=classification.query_type,
            file_confidence=file_confidence,
            sheet_confidence=sheet_confidence,
            trace_id=trace_id,
            processing_time_ms=int((time.time() - start_time) * 1000),
            from_cache=False
        )
        generation_time_ms = int((time.time() - generation_start) * 1000)
        
        # Complete trace
        self._trace_recorder.complete_trace(
            trace_id=trace_id,
            answer=response.answer,
            citations=[],
            confidence=response.confidence,
            generation_time_ms=generation_time_ms
        )
        
        # Clear pending state
        session.pending_query = None
        session.pending_clarification_type = None
        self._save_session(session)
        
        return response

    # =========================================================================
    # Selection Methods
    # =========================================================================

    def _select_file(
        self,
        query: str,
        user_id: Optional[str],
        file_hints: Optional[list[str]]
    ) -> FileSelectionResult:
        """
        Select file for query processing.
        
        Args:
            query: Query text.
            user_id: Optional user ID.
            file_hints: Optional file name hints.
            
        Returns:
            FileSelectionResult with candidates and action.
            
        Raises:
            SelectionError: If no files are indexed (Requirement 12.1).
        """
        try:
            # If file hints provided, incorporate into query
            enhanced_query = query
            if file_hints:
                enhanced_query = f"{query} (files: {', '.join(file_hints)})"
            
            return self._file_selector.rank_files(
                query=enhanced_query,
                user_id=user_id
            )
        except SelectionError as e:
            # Requirement 12.1: Return error for no indexed files
            if "No indexed files" in str(e):
                raise SelectionError(
                    "No files have been indexed yet. Please index some Excel files first "
                    "before running queries.",
                    details={"query": query[:100]}
                )
            raise

    def _select_sheets(
        self,
        file_id: str,
        query: str,
        sheet_hints: Optional[list[str]]
    ) -> SheetSelectionResult:
        """
        Select sheets for query processing.
        
        Args:
            file_id: ID of selected file.
            query: Query text.
            sheet_hints: Optional sheet name hints.
            
        Returns:
            SheetSelectionResult with candidates and action.
        """
        # If sheet hints provided, incorporate into query
        enhanced_query = query
        if sheet_hints:
            enhanced_query = f"{query} (sheets: {', '.join(sheet_hints)})"
        
        return self._sheet_selector.rank_sheets(
            file_id=file_id,
            query=enhanced_query
        )

    # =========================================================================
    # Clarification Creation Methods
    # =========================================================================

    def _create_file_clarification(
        self,
        file_result: FileSelectionResult,
        session: SessionContext,
        query: str,
        low_confidence: bool = False
    ) -> ClarificationRequest:
        """Create clarification request for file selection."""
        # Update session state
        session.pending_query = query
        session.pending_clarification_type = "file"
        session.file_selection_result = file_result
        self._save_session(session)
        
        # Build options
        options = []
        for candidate in file_result.candidates:
            options.append({
                "file_id": candidate.file_id,
                "file_name": candidate.file_name,
                "confidence": round(candidate.combined_score, 2),
                "semantic_score": round(candidate.semantic_score, 2),
                "metadata_score": round(candidate.metadata_score, 2)
            })
        
        message = file_result.message
        if low_confidence:
            message = (
                "I couldn't find a file that closely matches your query. "
                "Please select from the available files or rephrase your query."
            )
        
        return ClarificationRequest(
            clarification_type="file",
            message=message,
            options=options,
            session_id=session.session_id,
            pending_query=query
        )

    def _create_sheet_clarification(
        self,
        sheet_result: SheetSelectionResult,
        session: SessionContext,
        query: str
    ) -> ClarificationRequest:
        """Create clarification request for sheet selection."""
        # Update session state
        session.pending_query = query
        session.pending_clarification_type = "sheet"
        session.sheet_selection_result = sheet_result
        self._save_session(session)
        
        # Build options
        options = []
        for candidate in sheet_result.candidates:
            options.append({
                "sheet_name": candidate.sheet_name,
                "confidence": round(candidate.combined_score, 2),
                "name_score": round(candidate.name_score, 2),
                "header_score": round(candidate.header_score, 2)
            })
        
        return ClarificationRequest(
            clarification_type="sheet",
            message=sheet_result.message,
            options=options,
            session_id=session.session_id,
            pending_query=query
        )


    # =========================================================================
    # Session Management
    # =========================================================================

    def _get_or_create_session(self, session_id: str) -> SessionContext:
        """Get existing session or create new one."""
        session_data = self._session_store.get_session(session_id)
        if session_data:
            return SessionContext.from_dict(session_data)
        return SessionContext(session_id=session_id)

    def _get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get existing session or None."""
        session_data = self._session_store.get_session(session_id)
        if session_data:
            return SessionContext.from_dict(session_data)
        return None

    def _save_session(self, session: SessionContext) -> None:
        """Save session to store."""
        self._session_store.set_session(
            session_id=session.session_id,
            context=session.to_dict(),
            ttl=self._config.session_ttl_seconds
        )

    # =========================================================================
    # Caching
    # =========================================================================

    def _generate_cache_key(
        self,
        query: str,
        file_hints: Optional[list[str]],
        sheet_hints: Optional[list[str]]
    ) -> str:
        """Generate cache key for query."""
        key_parts = [query.lower().strip()]
        if file_hints:
            key_parts.append(f"files:{','.join(sorted(file_hints))}")
        if sheet_hints:
            key_parts.append(f"sheets:{','.join(sorted(sheet_hints))}")
        
        key_string = "|".join(key_parts)
        return f"query_cache:{hashlib.sha256(key_string.encode()).hexdigest()[:32]}"

    def _check_cache(
        self,
        query: str,
        file_hints: Optional[list[str]],
        sheet_hints: Optional[list[str]]
    ) -> Optional[QueryResponse]:
        """Check cache for existing response."""
        cache_key = self._generate_cache_key(query, file_hints, sheet_hints)
        cached = self._cache_service.get(cache_key)
        
        if cached and isinstance(cached, dict):
            try:
                response = QueryResponse(**cached)
                response.from_cache = True
                return response
            except Exception as e:
                logger.warning(f"Failed to deserialize cached response: {e}")
        
        return None

    def _cache_response(
        self,
        query: str,
        file_hints: Optional[list[str]],
        sheet_hints: Optional[list[str]],
        response: QueryResponse
    ) -> None:
        """Cache query response."""
        cache_key = self._generate_cache_key(query, file_hints, sheet_hints)
        try:
            self._cache_service.set(
                key=cache_key,
                value=response.model_dump(),
                ttl=self._config.cache_ttl_seconds
            )
        except Exception as e:
            logger.warning(f"Failed to cache response: {e}")

    # =========================================================================
    # Timeout Handling
    # =========================================================================

    def _execute_with_timeout(
        self,
        func: Any,
        **kwargs: Any
    ) -> Any:
        """
        Execute function with timeout.
        
        Implements Requirement 12.6: Timeout handling with configurable limit.
        
        Args:
            func: Function to execute.
            **kwargs: Arguments to pass to function.
            
        Returns:
            Function result.
            
        Raises:
            FuturesTimeoutError: If execution exceeds timeout.
        """
        future = self._executor.submit(func, **kwargs)
        return future.result(timeout=self._config.timeout_seconds)

    # =========================================================================
    # Error Handling Helpers
    # =========================================================================

    def _find_similar_names(
        self,
        target: str,
        candidates: list[str]
    ) -> list[str]:
        """
        Find similar names for suggestions.
        
        Implements Requirement 12.4: Return suggestions for similar names.
        
        Args:
            target: Target name to match.
            candidates: List of candidate names.
            
        Returns:
            List of similar names above threshold.
        """
        similarities = []
        target_lower = target.lower()
        
        for candidate in candidates:
            ratio = SequenceMatcher(None, target_lower, candidate.lower()).ratio()
            if ratio >= self._config.similarity_threshold:
                similarities.append((candidate, ratio))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return [name for name, _ in similarities[:self._config.max_suggestions]]

    def _handle_processing_error(
        self,
        error: Exception,
        query: str,
        trace_id: str,
        context: str = "query processing"
    ) -> QueryError:
        """
        Handle processing errors with user-friendly messages.
        
        Implements Requirements 12.3, 12.5:
        - 12.3: Return error for data type issues
        - 12.5: Log full error details with correlation ID
        
        Args:
            error: The original exception.
            query: The query being processed.
            trace_id: Trace ID for correlation.
            context: Context description for the error.
            
        Returns:
            QueryError with user-friendly message.
        """
        # Log full error details with correlation ID
        logger.error(
            f"Error during {context}: {error}",
            exc_info=True,
            extra={
                "trace_id": trace_id,
                "query": query[:100],
                "error_type": type(error).__name__
            }
        )
        
        # Determine user-friendly message based on error type
        if isinstance(error, ProcessingError):
            # Check for data type issues (Requirement 12.3)
            error_msg = str(error)
            if "numeric" in error_msg.lower() or "data type" in error_msg.lower():
                return QueryError(
                    "The data in the selected column(s) is not numeric and cannot be "
                    "aggregated. Please check that you're querying the correct column "
                    "or try a different query type.",
                    details={
                        "trace_id": trace_id,
                        "original_error": error_msg,
                        "suggestion": "Try using a lookup query instead of aggregation"
                    }
                )
            return QueryError(
                f"Unable to process your query: {error_msg}. "
                f"Please try rephrasing your question. (Error ID: {trace_id})",
                details={"trace_id": trace_id, "original_error": error_msg}
            )
        
        if isinstance(error, SelectionError):
            return QueryError(
                f"Could not find the requested data: {error}. "
                f"Please verify the file or sheet name and try again. "
                f"(Error ID: {trace_id})",
                details={"trace_id": trace_id, "original_error": str(error)}
            )
        
        # Generic error message for unexpected errors
        return QueryError(
            f"An unexpected error occurred while processing your query. "
            f"Please try again or contact support with Error ID: {trace_id}",
            details={
                "trace_id": trace_id,
                "error_type": type(error).__name__,
                "original_error": str(error)
            }
        )

    def _create_no_indexed_files_error(self, query: str, trace_id: str) -> SelectionError:
        """
        Create error for no indexed files scenario.
        
        Implements Requirement 12.1: Return error suggesting user index files first.
        
        Args:
            query: The query being processed.
            trace_id: Trace ID for correlation.
            
        Returns:
            SelectionError with helpful message.
        """
        logger.warning(
            f"No indexed files available for query",
            extra={"trace_id": trace_id, "query": query[:100]}
        )
        
        return SelectionError(
            "No Excel files have been indexed yet. Please index some files first:\n"
            "1. Upload Excel files through the API or UI\n"
            "2. Wait for indexing to complete\n"
            "3. Then try your query again",
            details={
                "trace_id": trace_id,
                "query": query[:100],
                "action_required": "index_files"
            }
        )

    def _create_ambiguous_data_error(
        self,
        query: str,
        trace_id: str,
        ambiguity_type: str,
        options: list[str]
    ) -> SelectionError:
        """
        Create error for ambiguous data scenarios.
        
        Implements Requirement 12.2: Return clarification request for ambiguous data.
        
        Args:
            query: The query being processed.
            trace_id: Trace ID for correlation.
            ambiguity_type: Type of ambiguity (file, sheet, column).
            options: Available options to choose from.
            
        Returns:
            SelectionError with available options.
        """
        logger.info(
            f"Ambiguous {ambiguity_type} selection for query",
            extra={
                "trace_id": trace_id,
                "query": query[:100],
                "options_count": len(options)
            }
        )
        
        options_text = ", ".join(options[:5])
        if len(options) > 5:
            options_text += f", and {len(options) - 5} more"
        
        return SelectionError(
            f"Multiple {ambiguity_type}s match your query. "
            f"Please specify which one you mean: {options_text}",
            details={
                "trace_id": trace_id,
                "ambiguity_type": ambiguity_type,
                "available_options": options,
                "action_required": "clarify_selection"
            }
        )

    def _create_not_found_error(
        self,
        query: str,
        trace_id: str,
        resource_type: str,
        resource_name: str,
        suggestions: list[str]
    ) -> SelectionError:
        """
        Create error for resource not found scenarios.
        
        Implements Requirement 12.4: Return suggestions for similar names.
        
        Args:
            query: The query being processed.
            trace_id: Trace ID for correlation.
            resource_type: Type of resource (file, sheet).
            resource_name: Name that was not found.
            suggestions: Similar names to suggest.
            
        Returns:
            SelectionError with suggestions.
        """
        logger.warning(
            f"{resource_type.capitalize()} not found: {resource_name}",
            extra={
                "trace_id": trace_id,
                "query": query[:100],
                "suggestions": suggestions
            }
        )
        
        message = f"The {resource_type} '{resource_name}' was not found."
        if suggestions:
            message += f" Did you mean: {', '.join(suggestions)}?"
        else:
            message += f" Please check the {resource_type} name and try again."
        
        return SelectionError(
            message,
            details={
                "trace_id": trace_id,
                "resource_type": resource_type,
                "resource_name": resource_name,
                "suggestions": suggestions,
                "action_required": "correct_name"
            }
        )

    # =========================================================================
    # Cleanup
    # =========================================================================

    def shutdown(self) -> None:
        """Shutdown the orchestrator and cleanup resources."""
        logger.info("Shutting down QueryPipelineOrchestrator")
        self._executor.shutdown(wait=True)
