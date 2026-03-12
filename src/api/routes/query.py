"""
Query Pipeline API Routes

This module provides API endpoints for the smart Excel query pipeline,
including natural language query processing, clarification handling,
query classification, and traceability endpoints.

Endpoints:
- POST /api/v1/query/smart - Process natural language query
- POST /api/v1/query/clarify - Respond to clarification request
- GET /api/v1/query/classify - Get query classification
- GET /api/v1/query/trace/{trace_id} - Get query trace
- GET /api/v1/lineage/{lineage_id} - Get data lineage
- Streaming support via Server-Sent Events for long queries

Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 16.3, 17.3
"""

import logging
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.exceptions import (
    ClassificationError,
    LineageError,
    ProcessingError,
    QueryError,
    SelectionError,
    TraceError,
)
from src.models.query_pipeline import (
    ClarificationRequest as ClarificationRequestModel,
    QueryClassification,
    QueryResponse,
    QueryType,
)
from src.models.traceability import DataLineage, QueryTrace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])


# ============================================================================
# Request/Response Models
# ============================================================================


class SmartQueryRequest(BaseModel):
    """
    Request model for smart query processing.
    
    Requirements: 14.1
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Natural language query to process"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for multi-turn conversation context"
    )
    file_hints: Optional[list[str]] = Field(
        default=None,
        description="Optional file IDs or names to guide file selection"
    )
    sheet_hints: Optional[list[str]] = Field(
        default=None,
        description="Optional sheet names to guide sheet selection"
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response via Server-Sent Events"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is the total sales for Q1 2024?",
                "session_id": "sess_abc123",
                "file_hints": ["sales_2024.xlsx"],
                "sheet_hints": None,
                "stream": False
            }
        }


class ClarificationResponse(BaseModel):
    """
    Request model for responding to a clarification request.
    
    Requirements: 14.2
    """
    session_id: str = Field(
        ...,
        description="Session ID from the clarification request"
    )
    clarification_type: str = Field(
        ...,
        description="Type of clarification: 'file', 'sheet', or 'query_type'"
    )
    selected_value: str = Field(
        ...,
        description="User's selected value (file_id, sheet_name, or query_type)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "clarification_type": "file",
                "selected_value": "file_123"
            }
        }


class ClassifyQueryRequest(BaseModel):
    """
    Request model for query classification.
    
    Requirements: 14.3
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Query text to classify"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is the total revenue for Q1?"
            }
        }


class ClassificationResponse(BaseModel):
    """
    Response model for query classification.
    
    Requirements: 14.3, 14.5
    """
    query_type: str = Field(
        ...,
        description="Classified query type"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Classification confidence score"
    )
    alternative_types: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Alternative classifications when confidence < 0.6"
    )
    detected_aggregations: list[str] = Field(
        default_factory=list,
        description="Detected aggregation functions"
    )
    detected_filters: list[str] = Field(
        default_factory=list,
        description="Detected filter conditions"
    )
    detected_columns: list[str] = Field(
        default_factory=list,
        description="Detected column references"
    )
    processing_time_ms: int = Field(
        ...,
        ge=0,
        description="Classification processing time in milliseconds"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query_type": "aggregation",
                "confidence": 0.95,
                "alternative_types": [],
                "detected_aggregations": ["SUM"],
                "detected_filters": ["Q1"],
                "detected_columns": ["revenue"],
                "processing_time_ms": 45
            }
        }


class QueryTraceResponse(BaseModel):
    """
    Response model for query trace retrieval.
    
    Requirements: 16.3, 14.5
    """
    trace_id: str
    query_text: str
    timestamp: str
    user_id: Optional[str]
    session_id: Optional[str]
    file_selection: dict[str, Any]
    sheet_selection: dict[str, Any]
    classification: dict[str, Any]
    retrieval: dict[str, Any]
    answer: dict[str, Any]
    performance: dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "trace_id": "tr_abc123",
                "query_text": "What is the total sales?",
                "timestamp": "2024-01-15T10:30:00Z",
                "user_id": "user_123",
                "session_id": "sess_abc123",
                "file_selection": {
                    "selected_file_id": "file_123",
                    "confidence": 0.95,
                    "reasoning": "High semantic match"
                },
                "sheet_selection": {
                    "selected_sheets": ["Sales"],
                    "confidence": 0.92
                },
                "classification": {
                    "query_type": "aggregation",
                    "confidence": 0.98
                },
                "retrieval": {
                    "chunks_count": 5
                },
                "answer": {
                    "confidence": 0.94,
                    "citations_count": 2
                },
                "performance": {
                    "total_time_ms": 450
                }
            }
        }


class DataLineageResponse(BaseModel):
    """
    Response model for data lineage retrieval.
    
    Requirements: 17.3, 14.5
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

    class Config:
        json_schema_extra = {
            "example": {
                "lineage_id": "lin_abc123",
                "answer_component": "Total sales: $1,234,567",
                "file_id": "file_123",
                "file_name": "sales_2024.xlsx",
                "sheet_name": "Q1",
                "cell_range": "B2:B100",
                "source_value": "1234567",
                "chunk_id": "chunk_456",
                "embedding_id": "emb_789",
                "retrieval_score": 0.95,
                "indexed_at": "2024-01-10T08:00:00Z",
                "last_verified_at": "2024-01-15T10:30:00Z",
                "is_stale": False,
                "stale_reason": None
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    detail: str
    correlation_id: str
    timestamp: str

    class Config:
        json_schema_extra = {
            "example": {
                "error": "QueryError",
                "detail": "No indexed files found",
                "correlation_id": "corr_abc123",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


# ============================================================================
# Dependency Injection
# ============================================================================


def get_query_pipeline_orchestrator():
    """
    Get QueryPipelineOrchestrator service instance.
    
    This is a placeholder that should be replaced with proper DI container
    integration in src/container.py.
    """
    from src.abstractions.cache_service_factory import CacheServiceFactory
    from src.abstractions.embedding_service_factory import EmbeddingServiceFactory
    from src.abstractions.llm_service_factory import LLMServiceFactory
    from src.abstractions.vector_store_factory import VectorStoreFactory
    from src.config import get_config
    from src.database.connection import DatabaseConnection
    from src.query_pipeline.answer_generator import AnswerGenerator
    from src.query_pipeline.classifier import QueryClassifier
    from src.query_pipeline.file_selector import FileSelector
    from src.query_pipeline.orchestrator import (
        QueryPipelineConfig,
        QueryPipelineOrchestrator,
    )
    from src.query_pipeline.sheet_selector import SheetSelector
    from src.traceability.lineage_storage import LineageStorage
    from src.traceability.lineage_tracker import DataLineageTracker
    from src.traceability.trace_recorder import TraceRecorder
    from src.traceability.trace_storage import TraceStorage
    
    try:
        config = get_config()
        db_connection = DatabaseConnection(db_path=config.database.db_path)
        
        # Create services
        vector_store = VectorStoreFactory.create(
            config.vector_store.provider,
            config.vector_store.config
        )
        embedding_service = EmbeddingServiceFactory.create(
            config.embedding.provider,
            config.embedding.config
        )
        llm_service = LLMServiceFactory.create(
            config.llm.provider,
            config.llm.config
        )
        cache_service = CacheServiceFactory.create(
            config.cache.backend,
            config.cache.config
        )
        
        # Create pipeline components
        file_selector = FileSelector(
            vector_store=vector_store,
            embedding_service=embedding_service,
            db_connection=db_connection,
        )
        sheet_selector = SheetSelector(
            vector_store=vector_store,
            embedding_service=embedding_service,
        )
        query_classifier = QueryClassifier(
            llm_service=llm_service,
            embedding_service=embedding_service,
        )
        answer_generator = AnswerGenerator(
            llm_service=llm_service,
        )
        
        # Create traceability components
        trace_storage = TraceStorage(db_connection=db_connection)
        trace_recorder = TraceRecorder(storage=trace_storage)
        lineage_storage = LineageStorage(db_connection=db_connection)
        lineage_tracker = DataLineageTracker(storage=lineage_storage)
        
        # Create a simple data retriever
        class SimpleDataRetriever:
            def __init__(self, vs, es):
                self._vector_store = vs
                self._embedding_service = es
            
            def retrieve_data(self, file_id, sheet_names, query, max_chunks=20):
                from src.query_pipeline.processors.base import RetrievedData
                # Simple retrieval implementation
                query_embedding = self._embedding_service.embed_text(query)
                results = self._vector_store.search(
                    query_embedding=query_embedding,
                    top_k=max_chunks,
                    filter_metadata={"file_id": file_id}
                )
                return RetrievedData(
                    chunks=[r.get("text", "") for r in results],
                    chunk_ids=[r.get("id", "") for r in results],
                    file_id=file_id,
                    sheet_names=sheet_names,
                )
        
        data_retriever = SimpleDataRetriever(vector_store, embedding_service)
        
        return QueryPipelineOrchestrator(
            file_selector=file_selector,
            sheet_selector=sheet_selector,
            query_classifier=query_classifier,
            answer_generator=answer_generator,
            trace_recorder=trace_recorder,
            data_retriever=data_retriever,
            session_store=cache_service,
            cache_service=cache_service,
            config=QueryPipelineConfig(),
        )
    except Exception as e:
        logger.error(f"Failed to initialize QueryPipelineOrchestrator: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service initialization failed: {str(e)}"
        )


def get_query_classifier():
    """Get QueryClassifier service instance."""
    from src.abstractions.embedding_service_factory import EmbeddingServiceFactory
    from src.abstractions.llm_service_factory import LLMServiceFactory
    from src.config import get_config
    from src.query_pipeline.classifier import QueryClassifier
    
    try:
        config = get_config()
        embedding_service = EmbeddingServiceFactory.create(
            config.embedding.provider,
            config.embedding.config
        )
        llm_service = LLMServiceFactory.create(
            config.llm.provider,
            config.llm.config
        )
        return QueryClassifier(
            llm_service=llm_service,
            embedding_service=embedding_service,
        )
    except Exception as e:
        logger.error(f"Failed to initialize QueryClassifier: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service initialization failed: {str(e)}"
        )


def get_trace_recorder():
    """Get TraceRecorder service instance."""
    from src.config import get_config
    from src.database.connection import DatabaseConnection
    from src.traceability.trace_recorder import TraceRecorder
    from src.traceability.trace_storage import TraceStorage
    
    try:
        config = get_config()
        db_connection = DatabaseConnection(db_path=config.database.db_path)
        trace_storage = TraceStorage(db_connection=db_connection)
        return TraceRecorder(storage=trace_storage)
    except Exception as e:
        logger.error(f"Failed to initialize TraceRecorder: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service initialization failed: {str(e)}"
        )


def get_lineage_tracker():
    """Get DataLineageTracker service instance."""
    from src.config import get_config
    from src.database.connection import DatabaseConnection
    from src.traceability.lineage_storage import LineageStorage
    from src.traceability.lineage_tracker import DataLineageTracker
    
    try:
        config = get_config()
        db_connection = DatabaseConnection(db_path=config.database.db_path)
        lineage_storage = LineageStorage(db_connection=db_connection)
        return DataLineageTracker(storage=lineage_storage)
    except Exception as e:
        logger.error(f"Failed to initialize DataLineageTracker: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service initialization failed: {str(e)}"
        )


async def get_correlation_id(
    x_correlation_id: Optional[str] = Header(None)
) -> str:
    """Get or generate correlation ID for request tracing."""
    return x_correlation_id or str(uuid.uuid4())


# ============================================================================
# Query Pipeline Endpoints
# ============================================================================


@router.post(
    "/query/smart",
    response_model=Union[QueryResponse, ClarificationRequestModel],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        408: {"model": ErrorResponse, "description": "Request timeout"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Process natural language query",
    description="Process a natural language query through the smart Excel query pipeline. "
                "Returns either a QueryResponse with the answer or a ClarificationRequest "
                "if user input is needed. Supports streaming via Server-Sent Events."
)
async def process_smart_query(
    request: SmartQueryRequest,
    orchestrator=Depends(get_query_pipeline_orchestrator),
    correlation_id: str = Depends(get_correlation_id),
    x_user_id: Optional[str] = Header(None)
) -> Union[QueryResponse, ClarificationRequestModel, StreamingResponse]:
    """
    Process a natural language query through the full pipeline.
    
    Coordinates file selection, sheet selection, query classification,
    processing, and answer generation. Returns either a QueryResponse
    with the answer or a ClarificationRequest if user input is needed.
    
    Requirements: 14.1, 14.4, 14.5
    """
    logger.info(
        f"POST /query/smart - query='{request.query[:50]}...', "
        f"session_id={request.session_id}, correlation_id={correlation_id}"
    )
    
    # Handle streaming response
    if request.stream:
        return StreamingResponse(
            _stream_query_response(
                orchestrator=orchestrator,
                query=request.query,
                session_id=request.session_id,
                user_id=x_user_id,
                file_hints=request.file_hints,
                sheet_hints=request.sheet_hints,
            ),
            media_type="text/event-stream"
        )
    
    try:
        result = orchestrator.process_query(
            query=request.query,
            session_id=request.session_id,
            user_id=x_user_id,
            file_hints=request.file_hints,
            sheet_hints=request.sheet_hints,
        )
        return result
        
    except QueryError as e:
        logger.error(
            f"QueryError processing query: {e}",
            extra={"correlation_id": correlation_id}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except SelectionError as e:
        logger.error(
            f"SelectionError processing query: {e}",
            extra={"correlation_id": correlation_id}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ProcessingError as e:
        logger.error(
            f"ProcessingError processing query: {e}",
            extra={"correlation_id": correlation_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


async def _stream_query_response(
    orchestrator,
    query: str,
    session_id: Optional[str],
    user_id: Optional[str],
    file_hints: Optional[list[str]],
    sheet_hints: Optional[list[str]],
) -> AsyncGenerator[str, None]:
    """
    Stream query response via Server-Sent Events.
    
    Requirements: 14.4
    """
    import json
    import time
    
    try:
        # Send processing started event
        yield f"event: processing\ndata: {json.dumps({'status': 'started'})}\n\n"
        
        start_time = time.time()
        
        # Process query
        result = orchestrator.process_query(
            query=query,
            session_id=session_id,
            user_id=user_id,
            file_hints=file_hints,
            sheet_hints=sheet_hints,
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Send result event
        if isinstance(result, QueryResponse):
            yield f"event: answer\ndata: {result.model_dump_json()}\n\n"
        else:
            yield f"event: clarification\ndata: {result.model_dump_json()}\n\n"
        
        # Send completion event
        yield f"event: complete\ndata: {json.dumps({'processing_time_ms': processing_time_ms})}\n\n"
        
    except Exception as e:
        logger.error(f"Error in streaming response: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


@router.post(
    "/query/clarify",
    response_model=Union[QueryResponse, ClarificationRequestModel],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Session not found"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Respond to clarification request",
    description="Submit user's response to a clarification request and continue "
                "query processing with the selected value."
)
async def respond_to_clarification(
    request: ClarificationResponse,
    orchestrator=Depends(get_query_pipeline_orchestrator),
    correlation_id: str = Depends(get_correlation_id)
) -> Union[QueryResponse, ClarificationRequestModel]:
    """
    Handle user response to a clarification request.
    
    Continues query processing with the user's selection.
    
    Requirements: 14.2
    """
    logger.info(
        f"POST /query/clarify - session_id={request.session_id}, "
        f"type={request.clarification_type}, correlation_id={correlation_id}"
    )
    
    try:
        result = orchestrator.handle_clarification(
            session_id=request.session_id,
            clarification_type=request.clarification_type,
            selected_value=request.selected_value,
        )
        return result
        
    except QueryError as e:
        logger.error(
            f"QueryError handling clarification: {e}",
            extra={"correlation_id": correlation_id}
        )
        if "not found" in str(e).lower() or "expired" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/query/classify",
    response_model=ClassificationResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get query classification",
    description="Classify a query into one of the supported types: "
                "aggregation, lookup, summarization, or comparison."
)
async def classify_query(
    query: str = Query(
        ...,
        min_length=1,
        max_length=5000,
        description="Query text to classify"
    ),
    classifier=Depends(get_query_classifier),
    correlation_id: str = Depends(get_correlation_id)
) -> ClassificationResponse:
    """
    Get query type classification for a given query.
    
    Returns the classified type, confidence score, and extracted parameters.
    
    Requirements: 14.3, 14.5
    """
    import time
    
    logger.info(
        f"GET /query/classify - query='{query[:50]}...', "
        f"correlation_id={correlation_id}"
    )
    
    try:
        start_time = time.time()
        classification = classifier.classify(query)
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return ClassificationResponse(
            query_type=classification.query_type.value,
            confidence=classification.confidence,
            alternative_types=[
                {"type": t.value, "confidence": c}
                for t, c in classification.alternative_types
            ],
            detected_aggregations=classification.detected_aggregations,
            detected_filters=classification.detected_filters,
            detected_columns=classification.detected_columns,
            processing_time_ms=processing_time_ms,
        )
        
    except ClassificationError as e:
        logger.error(
            f"ClassificationError: {e}",
            extra={"correlation_id": correlation_id}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# Traceability Endpoints
# ============================================================================


@router.get(
    "/query/trace/{trace_id}",
    response_model=QueryTraceResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Trace not found"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get query trace",
    description="Retrieve the complete decision trail for a query, including "
                "file selection, sheet selection, classification, and answer generation."
)
async def get_query_trace(
    trace_id: str,
    trace_recorder=Depends(get_trace_recorder),
    correlation_id: str = Depends(get_correlation_id)
) -> QueryTraceResponse:
    """
    Retrieve a completed trace by ID.
    
    Returns the complete decision trail for audit and debugging.
    
    Requirements: 16.3, 14.5
    """
    logger.info(
        f"GET /query/trace/{trace_id} - correlation_id={correlation_id}"
    )
    
    try:
        trace = trace_recorder.get_trace(trace_id)
        
        if trace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trace not found: {trace_id}"
            )
        
        return QueryTraceResponse(
            trace_id=trace.trace_id,
            query_text=trace.query_text,
            timestamp=trace.timestamp,
            user_id=trace.user_id,
            session_id=trace.session_id,
            file_selection={
                "selected_file_id": trace.selected_file_id,
                "confidence": trace.file_confidence,
                "reasoning": trace.file_selection_reasoning,
                "candidates_count": len(trace.file_candidates),
            },
            sheet_selection={
                "selected_sheets": trace.selected_sheets,
                "confidence": trace.sheet_confidence,
                "reasoning": trace.sheet_selection_reasoning,
                "candidates_count": len(trace.sheet_candidates),
            },
            classification={
                "query_type": trace.query_type.value if trace.query_type else None,
                "confidence": trace.classification_confidence,
            },
            retrieval={
                "chunks_count": len(trace.chunks_retrieved),
                "chunk_ids": trace.chunks_retrieved,
            },
            answer={
                "text": trace.answer_text,
                "confidence": trace.answer_confidence,
                "citations_count": len(trace.citations),
            },
            performance={
                "total_time_ms": trace.total_processing_time_ms,
                "file_selection_time_ms": trace.file_selection_time_ms,
                "sheet_selection_time_ms": trace.sheet_selection_time_ms,
                "retrieval_time_ms": trace.retrieval_time_ms,
                "generation_time_ms": trace.generation_time_ms,
            },
        )
        
    except TraceError as e:
        logger.error(
            f"TraceError getting trace: {e}",
            extra={"correlation_id": correlation_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/lineage/{lineage_id}",
    response_model=DataLineageResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Lineage not found"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get data lineage",
    description="Retrieve the complete data path from source Excel cell to answer component."
)
async def get_data_lineage(
    lineage_id: str,
    lineage_tracker=Depends(get_lineage_tracker),
    correlation_id: str = Depends(get_correlation_id)
) -> DataLineageResponse:
    """
    Retrieve a lineage record by ID.
    
    Returns the complete data path from source to answer for compliance verification.
    
    Requirements: 17.3, 14.5
    """
    logger.info(
        f"GET /lineage/{lineage_id} - correlation_id={correlation_id}"
    )
    
    try:
        lineage = lineage_tracker.get_lineage(lineage_id)
        
        if lineage is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lineage not found: {lineage_id}"
            )
        
        return DataLineageResponse(
            lineage_id=lineage.lineage_id,
            answer_component=lineage.answer_component,
            file_id=lineage.file_id,
            file_name=lineage.file_name,
            sheet_name=lineage.sheet_name,
            cell_range=lineage.cell_range,
            source_value=lineage.source_value,
            chunk_id=lineage.chunk_id,
            embedding_id=lineage.embedding_id,
            retrieval_score=lineage.retrieval_score,
            indexed_at=lineage.indexed_at,
            last_verified_at=lineage.last_verified_at,
            is_stale=lineage.is_stale,
            stale_reason=lineage.stale_reason,
        )
        
    except LineageError as e:
        logger.error(
            f"LineageError getting lineage: {e}",
            extra={"correlation_id": correlation_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
