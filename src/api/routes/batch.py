"""
Batch and Template API Routes

This module provides API endpoints for batch query processing and
query template management.

Endpoints:
- POST /api/v1/query/batch - Submit batch queries
- GET /api/v1/query/batch/{batch_id}/status - Get batch status
- POST /api/v1/query/templates - Create template
- POST /api/v1/query/templates/{template_id}/execute - Execute template
- GET /api/v1/query/templates - List templates

Requirements: 24.1, 24.5, 25.1, 25.3, 25.4
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.exceptions import BatchError, TemplateError
from src.models.enterprise import BatchQueryRequest, BatchQueryStatus, QueryTemplate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/query", tags=["batch", "templates"])


# ============================================================================
# Request/Response Models
# ============================================================================


class BatchSubmitResponse(BaseModel):
    """Response model for batch submission."""
    batch_id: str = Field(..., description="Unique batch identifier")
    total_queries: int = Field(..., description="Number of queries submitted")
    status: str = Field(..., description="Initial batch status")
    message: str = Field(..., description="Status message")

    class Config:
        json_schema_extra = {
            "example": {
                "batch_id": "batch_abc123",
                "total_queries": 10,
                "status": "processing",
                "message": "Batch submitted successfully"
            }
        }


class TemplateCreateRequest(BaseModel):
    """Request model for creating a query template."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable template name"
    )
    template_text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Template text with {{parameter}} placeholders"
    )
    is_shared: bool = Field(
        default=False,
        description="Whether to share with organization"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Quarterly Revenue Report",
                "template_text": "What is the total {{metric}} for {{period}}?",
                "is_shared": True
            }
        }


class TemplateResponse(BaseModel):
    """Response model for template operations."""
    template_id: str
    name: str
    template_text: str
    parameters: list[str]
    created_by: str
    created_at: str
    is_shared: bool

    class Config:
        json_schema_extra = {
            "example": {
                "template_id": "tmpl_abc123",
                "name": "Quarterly Revenue Report",
                "template_text": "What is the total {{metric}} for {{period}}?",
                "parameters": ["metric", "period"],
                "created_by": "user_123",
                "created_at": "2024-01-15T10:30:00Z",
                "is_shared": True
            }
        }


class TemplateExecuteRequest(BaseModel):
    """Request model for executing a template."""
    parameters: dict[str, str] = Field(
        ...,
        description="Parameter values to substitute in the template"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for context"
    )
    file_hints: Optional[list[str]] = Field(
        default=None,
        description="Optional file hints"
    )
    sheet_hints: Optional[list[str]] = Field(
        default=None,
        description="Optional sheet hints"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "parameters": {
                    "metric": "revenue",
                    "period": "Q1 2024"
                },
                "session_id": None,
                "file_hints": None,
                "sheet_hints": None
            }
        }


class TemplateExecuteResponse(BaseModel):
    """Response model for template execution."""
    template_id: str
    substituted_query: str
    response: dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "template_id": "tmpl_abc123",
                "substituted_query": "What is the total revenue for Q1 2024?",
                "response": {
                    "answer": "The total revenue for Q1 2024 is $1,234,567",
                    "confidence": 0.95
                }
            }
        }


class TemplateListResponse(BaseModel):
    """Response model for listing templates."""
    templates: list[TemplateResponse]
    total_count: int

    class Config:
        json_schema_extra = {
            "example": {
                "templates": [],
                "total_count": 0
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    detail: str
    correlation_id: str
    timestamp: str


# ============================================================================
# Dependency Injection
# ============================================================================


def get_batch_processor():
    """Get BatchQueryProcessor service instance."""
    from src.batch.processor import BatchProcessorConfig, BatchQueryProcessor
    from src.batch.store import SQLiteBatchStore
    from src.config import get_config
    from src.database.connection import DatabaseConnection
    
    try:
        config = get_config()
        db_connection = DatabaseConnection(db_path=config.database.db_path)
        batch_store = SQLiteBatchStore(db_connection=db_connection)
        
        # Get query executor (orchestrator)
        orchestrator = _get_query_orchestrator()
        
        return BatchQueryProcessor(
            query_executor=orchestrator,
            batch_store=batch_store,
            config=BatchProcessorConfig(),
        )
    except Exception as e:
        logger.error(f"Failed to initialize BatchQueryProcessor: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service initialization failed: {str(e)}"
        )


def get_template_manager():
    """Get TemplateManager service instance."""
    from src.config import get_config
    from src.database.connection import DatabaseConnection
    from src.templates.manager import TemplateManager
    from src.templates.store import SQLiteTemplateStore
    
    try:
        config = get_config()
        db_connection = DatabaseConnection(db_path=config.database.db_path)
        template_store = SQLiteTemplateStore(db_connection=db_connection)
        
        # Get query executor (orchestrator)
        orchestrator = _get_query_orchestrator()
        
        return TemplateManager(
            query_executor=orchestrator,
            template_store=template_store,
        )
    except Exception as e:
        logger.error(f"Failed to initialize TemplateManager: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service initialization failed: {str(e)}"
        )


def _get_query_orchestrator():
    """Get QueryPipelineOrchestrator instance (shared helper)."""
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
    from src.query_pipeline.processors.base import RetrievedData
    from src.query_pipeline.sheet_selector import SheetSelector
    from src.traceability.trace_recorder import TraceRecorder
    from src.traceability.trace_storage import TraceStorage
    
    config = get_config()
    db_connection = DatabaseConnection(db_path=config.database.db_path)
    
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
    answer_generator = AnswerGenerator(llm_service=llm_service)
    
    trace_storage = TraceStorage(db_connection=db_connection)
    trace_recorder = TraceRecorder(storage=trace_storage)
    
    class SimpleDataRetriever:
        def __init__(self, vs, es):
            self._vector_store = vs
            self._embedding_service = es
        
        def retrieve_data(self, file_id, sheet_names, query, max_chunks=20):
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


async def get_correlation_id(
    x_correlation_id: Optional[str] = Header(None)
) -> str:
    """Get or generate correlation ID for request tracing."""
    return x_correlation_id or str(uuid.uuid4())


# ============================================================================
# Batch Query Endpoints
# ============================================================================


@router.post(
    "/batch",
    response_model=BatchQueryStatus,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Submit batch queries",
    description="Submit multiple queries for batch processing. Queries are processed "
                "in parallel where possible. Maximum 100 queries per batch."
)
async def submit_batch_queries(
    request: BatchQueryRequest,
    batch_processor=Depends(get_batch_processor),
    correlation_id: str = Depends(get_correlation_id),
    x_user_id: Optional[str] = Header(None)
) -> BatchQueryStatus:
    """
    Submit a batch of queries for processing.
    
    Requirements: 24.1
    """
    logger.info(
        f"POST /query/batch - {len(request.queries)} queries, "
        f"correlation_id={correlation_id}"
    )
    
    try:
        result = batch_processor.submit_batch(
            request=request,
            user_id=x_user_id,
        )
        return result
        
    except BatchError as e:
        logger.error(
            f"BatchError submitting batch: {e}",
            extra={"correlation_id": correlation_id}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/batch/{batch_id}/status",
    response_model=BatchQueryStatus,
    responses={
        404: {"model": ErrorResponse, "description": "Batch not found"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get batch status",
    description="Get the current status and results of a batch query request."
)
async def get_batch_status(
    batch_id: str,
    batch_processor=Depends(get_batch_processor),
    correlation_id: str = Depends(get_correlation_id)
) -> BatchQueryStatus:
    """
    Get the current status of a batch.
    
    Requirements: 24.5
    """
    logger.info(
        f"GET /query/batch/{batch_id}/status - correlation_id={correlation_id}"
    )
    
    result = batch_processor.get_batch_status(batch_id)
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch not found: {batch_id}"
        )
    
    return result


# ============================================================================
# Template Endpoints
# ============================================================================


@router.post(
    "/templates",
    response_model=TemplateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Create query template",
    description="Create a new parameterized query template with {{parameter}} syntax."
)
async def create_template(
    request: TemplateCreateRequest,
    template_manager=Depends(get_template_manager),
    correlation_id: str = Depends(get_correlation_id),
    x_user_id: Optional[str] = Header(None)
) -> TemplateResponse:
    """
    Create a new query template.
    
    Requirements: 25.1
    """
    logger.info(
        f"POST /query/templates - name='{request.name}', "
        f"correlation_id={correlation_id}"
    )
    
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id header is required"
        )
    
    try:
        template = template_manager.create_template(
            name=request.name,
            template_text=request.template_text,
            created_by=x_user_id,
            is_shared=request.is_shared,
        )
        
        return TemplateResponse(
            template_id=template.template_id,
            name=template.name,
            template_text=template.template_text,
            parameters=template.parameters,
            created_by=template.created_by,
            created_at=template.created_at.isoformat(),
            is_shared=template.is_shared,
        )
        
    except TemplateError as e:
        logger.error(
            f"TemplateError creating template: {e}",
            extra={"correlation_id": correlation_id}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/templates/{template_id}/execute",
    response_model=TemplateExecuteResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Template not found"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Execute query template",
    description="Execute a template with parameter substitution and return the query result."
)
async def execute_template(
    template_id: str,
    request: TemplateExecuteRequest,
    template_manager=Depends(get_template_manager),
    correlation_id: str = Depends(get_correlation_id),
    x_user_id: Optional[str] = Header(None)
) -> TemplateExecuteResponse:
    """
    Execute a template with parameter substitution.
    
    Requirements: 25.3
    """
    logger.info(
        f"POST /query/templates/{template_id}/execute - "
        f"correlation_id={correlation_id}"
    )
    
    try:
        result = template_manager.execute_template(
            template_id=template_id,
            parameters=request.parameters,
            user_id=x_user_id,
            session_id=request.session_id,
            file_hints=request.file_hints,
            sheet_hints=request.sheet_hints,
        )
        
        # Convert response to dict
        response_dict = {}
        if hasattr(result.response, 'model_dump'):
            response_dict = result.response.model_dump()
        elif hasattr(result.response, '__dict__'):
            response_dict = result.response.__dict__
        
        return TemplateExecuteResponse(
            template_id=result.template_id,
            substituted_query=result.substituted_query,
            response=response_dict,
        )
        
    except TemplateError as e:
        logger.error(
            f"TemplateError executing template: {e}",
            extra={"correlation_id": correlation_id}
        )
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/templates",
    response_model=TemplateListResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="List query templates",
    description="Get all templates accessible to the user, including shared templates."
)
async def list_templates(
    include_shared: bool = Query(
        True,
        description="Whether to include shared templates"
    ),
    template_manager=Depends(get_template_manager),
    correlation_id: str = Depends(get_correlation_id),
    x_user_id: Optional[str] = Header(None)
) -> TemplateListResponse:
    """
    Get all templates accessible to a user.
    
    Requirements: 25.4
    """
    logger.info(
        f"GET /query/templates - include_shared={include_shared}, "
        f"correlation_id={correlation_id}"
    )
    
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id header is required"
        )
    
    templates = template_manager.get_templates_for_user(
        user_id=x_user_id,
        include_shared=include_shared,
    )
    
    template_responses = [
        TemplateResponse(
            template_id=t.template_id,
            name=t.name,
            template_text=t.template_text,
            parameters=t.parameters,
            created_by=t.created_by,
            created_at=t.created_at.isoformat(),
            is_shared=t.is_shared,
        )
        for t in templates
    ]
    
    return TemplateListResponse(
        templates=template_responses,
        total_count=len(template_responses),
    )
