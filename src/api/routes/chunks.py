"""
Chunk Visibility API Routes

This module provides API endpoints for chunk visibility and debugging capabilities.
All endpoints follow RESTful conventions and return JSON responses with consistent schemas.

Endpoints:
- GET /api/v1/chunks/{file_id} - Get all chunks for a file with pagination
- GET /api/v1/chunks/{file_id}/sheets/{sheet_name} - Get chunks for a specific sheet
- POST /api/v1/chunks/search - Semantic search with filters
- GET /api/v1/files/{file_id}/extraction-metadata - Get extraction details
- GET /api/v1/chunks/{file_id}/versions - Get version history for file chunks
- POST /api/v1/chunks/{chunk_id}/feedback - Submit chunk quality feedback
- GET /api/v1/chunks/feedback-summary - Get aggregated feedback statistics
- GET /api/v1/files/quality-report - Get quality scores for all indexed files

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 21.2, 22.5, 27.1, 27.4
"""

import logging
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from pydantic import BaseModel, Field

from src.chunk_viewer.feedback import FeedbackCollector
from src.chunk_viewer.metadata_store import ChunkMetadataStore
from src.chunk_viewer.version_store import ChunkVersionStore
from src.chunk_viewer.viewer import ChunkViewer
from src.exceptions import ChunkViewerError
from src.models.chunk_visibility import (
    ChunkFeedback,
    ChunkFilters,
    ExtractionMetadata,
    PaginatedChunkResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chunks"])


# ============================================================================
# Configuration Constants
# ============================================================================

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


# ============================================================================
# Request/Response Models
# ============================================================================

class ChunkSearchRequest(BaseModel):
    """
    Request model for chunk semantic search.
    
    Requirements: 13.3
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text for semantic matching"
    )
    extraction_strategy: Optional[str] = Field(
        default=None,
        description="Filter by extraction strategy (openpyxl, docling, etc.)"
    )
    file_id: Optional[str] = Field(
        default=None,
        description="Filter by file ID"
    )
    sheet_name: Optional[str] = Field(
        default=None,
        description="Filter by sheet name"
    )
    content_type: Optional[str] = Field(
        default=None,
        description="Filter by content type"
    )
    min_quality_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum quality score filter (0.0 to 1.0)"
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed)"
    )
    page_size: int = Field(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Number of items per page (max 100)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "sales revenue Q1 2024",
                "file_id": "file_123",
                "page": 1,
                "page_size": 20
            }
        }


class ExtractionMetadataResponse(BaseModel):
    """
    Response model for extraction metadata.
    
    Requirements: 13.4, 13.5
    """
    file_id: str
    strategy_used: str
    strategy_selected_reason: Optional[str] = None
    complexity_score: Optional[float] = None
    quality_score: float
    has_headers: bool
    has_data: bool
    data_completeness: float
    structure_clarity: float
    extraction_errors: List[str] = Field(default_factory=list)
    extraction_warnings: List[str] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    extraction_duration_ms: int = 0
    extracted_at: str = ""

    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "file_123",
                "strategy_used": "openpyxl",
                "quality_score": 0.95,
                "has_headers": True,
                "has_data": True,
                "data_completeness": 0.98,
                "structure_clarity": 0.92,
                "extraction_errors": [],
                "extraction_warnings": [],
                "fallback_used": False,
                "extraction_duration_ms": 1250,
                "extracted_at": "2024-01-15T10:30:00Z"
            }
        }


class ChunkVersionResponse(BaseModel):
    """
    Response model for chunk version information.
    
    Requirements: 21.2
    """
    version_id: str
    chunk_id: str
    version_number: int
    chunk_text: str
    extraction_strategy: str
    indexed_at: str
    change_summary: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "version_id": "chunk_001_v2",
                "chunk_id": "chunk_001",
                "version_number": 2,
                "chunk_text": "Month,Revenue\nJan,10000",
                "extraction_strategy": "openpyxl",
                "indexed_at": "2024-01-15T10:30:00Z",
                "change_summary": "3 line(s) added, 1 line(s) removed"
            }
        }


class VersionHistoryResponse(BaseModel):
    """
    Response model for version history listing.
    
    Requirements: 13.5, 13.6, 21.2
    """
    file_id: str
    versions: List[Dict[str, Any]]
    total_count: int

    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "file_123",
                "versions": [
                    {
                        "chunk_id": "chunk_001",
                        "version_number": 2,
                        "indexed_at": "2024-01-15T10:30:00Z"
                    }
                ],
                "total_count": 5
            }
        }


class FeedbackSubmitRequest(BaseModel):
    """
    Request model for submitting chunk feedback.
    
    Requirements: 27.1
    """
    feedback_type: str = Field(
        ...,
        description="Type: incorrect_data, missing_data, wrong_boundaries, extraction_error, other"
    )
    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Quality rating from 1 (poor) to 5 (excellent)"
    )
    comment: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional detailed comment about the issue"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional user ID for tracking feedback source"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "feedback_type": "wrong_boundaries",
                "rating": 2,
                "comment": "Chunk splits a table in the middle of a data section",
                "user_id": "user_123"
            }
        }


class FeedbackSubmitResponse(BaseModel):
    """
    Response model for feedback submission.
    
    Requirements: 13.5, 27.1
    """
    feedback_id: str
    chunk_id: str
    feedback_type: str
    rating: int
    created_at: str
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "feedback_id": "fb_abc123",
                "chunk_id": "chunk_001",
                "feedback_type": "wrong_boundaries",
                "rating": 2,
                "created_at": "2024-01-15T10:30:00Z",
                "message": "Feedback submitted successfully"
            }
        }


class FeedbackSummaryResponse(BaseModel):
    """
    Response model for aggregated feedback statistics.
    
    Requirements: 13.5, 27.4
    """
    total_feedback_count: int
    total_chunks_with_feedback: int
    average_rating: float
    feedback_by_type: Dict[str, int]
    chunks_flagged_for_review: int
    top_problematic_chunks: List[str]
    generated_at: str

    class Config:
        json_schema_extra = {
            "example": {
                "total_feedback_count": 150,
                "total_chunks_with_feedback": 45,
                "average_rating": 3.5,
                "feedback_by_type": {
                    "incorrect_data": 20,
                    "missing_data": 15,
                    "wrong_boundaries": 30
                },
                "chunks_flagged_for_review": 8,
                "top_problematic_chunks": ["chunk_001", "chunk_042"],
                "generated_at": "2024-01-15T10:30:00Z"
            }
        }


class FileQualityReport(BaseModel):
    """
    Quality report for a single file.
    
    Requirements: 22.5
    """
    file_id: str
    file_name: Optional[str] = None
    quality_score: float
    has_headers: bool
    has_data: bool
    data_completeness: float
    structure_clarity: float
    extraction_strategy: str
    is_problematic: bool
    extracted_at: str


class QualityReportResponse(BaseModel):
    """
    Response model for quality report across all files.
    
    Requirements: 13.5, 13.6, 22.5
    """
    files: List[FileQualityReport]
    total_count: int
    page: int
    page_size: int
    has_more: bool
    average_quality_score: float
    problematic_files_count: int

    class Config:
        json_schema_extra = {
            "example": {
                "files": [
                    {
                        "file_id": "file_123",
                        "file_name": "sales_2024.xlsx",
                        "quality_score": 0.95,
                        "has_headers": True,
                        "has_data": True,
                        "data_completeness": 0.98,
                        "structure_clarity": 0.92,
                        "extraction_strategy": "openpyxl",
                        "is_problematic": False,
                        "extracted_at": "2024-01-15T10:30:00Z"
                    }
                ],
                "total_count": 25,
                "page": 1,
                "page_size": 20,
                "has_more": True,
                "average_quality_score": 0.85,
                "problematic_files_count": 3
            }
        }


class ErrorResponse(BaseModel):
    """
    Standard error response model.
    
    Requirements: 13.5
    """
    error: str
    detail: str
    correlation_id: str
    timestamp: str

    class Config:
        json_schema_extra = {
            "example": {
                "error": "NotFound",
                "detail": "File not found: file_123",
                "correlation_id": "corr_abc123",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


# ============================================================================
# Dependency Injection
# ============================================================================

def get_chunk_viewer() -> ChunkViewer:
    """
    Get ChunkViewer service instance with all dependencies.
    
    This is a placeholder that should be replaced with proper DI container
    integration in src/container.py.
    
    Returns:
        ChunkViewer instance with injected dependencies.
    
    Raises:
        HTTPException: If service initialization fails.
    """
    # Import here to avoid circular imports
    from src.abstractions.embedding_service_factory import EmbeddingServiceFactory
    from src.abstractions.vector_store_factory import VectorStoreFactory
    from src.config import get_config
    from src.database.connection import DatabaseConnection
    
    try:
        config = get_config()
        
        # Create database connection
        db_connection = DatabaseConnection(db_path=config.database.db_path)
        
        # Create stores
        metadata_store = ChunkMetadataStore(db_connection=db_connection)
        version_store = ChunkVersionStore(db_connection=db_connection)
        
        # Create vector store and embedding service
        vector_store = VectorStoreFactory.create(
            config.vector_store.provider,
            config.vector_store.config
        )
        embedding_service = EmbeddingServiceFactory.create(
            config.embedding.provider,
            config.embedding.config
        )
        
        return ChunkViewer(
            metadata_store=metadata_store,
            version_store=version_store,
            vector_store=vector_store,
            embedding_service=embedding_service,
        )
    except Exception as e:
        logger.error(f"Failed to initialize ChunkViewer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service initialization failed: {str(e)}"
        )


def get_chunk_version_store() -> ChunkVersionStore:
    """
    Get ChunkVersionStore instance.
    
    Returns:
        ChunkVersionStore instance.
    
    Raises:
        HTTPException: If initialization fails.
    """
    from src.config import get_config
    from src.database.connection import DatabaseConnection
    
    try:
        config = get_config()
        db_connection = DatabaseConnection(db_path=config.database.db_path)
        return ChunkVersionStore(db_connection=db_connection)
    except Exception as e:
        logger.error(f"Failed to initialize ChunkVersionStore: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service initialization failed: {str(e)}"
        )


def get_feedback_collector() -> FeedbackCollector:
    """
    Get FeedbackCollector service instance.
    
    Returns:
        FeedbackCollector instance.
    
    Raises:
        HTTPException: If initialization fails.
    """
    from src.chunk_viewer.feedback import SQLiteFeedbackStore
    from src.config import get_config
    from src.database.connection import DatabaseConnection
    
    try:
        config = get_config()
        db_connection = DatabaseConnection(db_path=config.database.db_path)
        feedback_store = SQLiteFeedbackStore(db_connection=db_connection)
        return FeedbackCollector(feedback_store=feedback_store)
    except Exception as e:
        logger.error(f"Failed to initialize FeedbackCollector: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service initialization failed: {str(e)}"
        )


def get_metadata_store() -> ChunkMetadataStore:
    """
    Get ChunkMetadataStore instance.
    
    Returns:
        ChunkMetadataStore instance.
    
    Raises:
        HTTPException: If initialization fails.
    """
    from src.config import get_config
    from src.database.connection import DatabaseConnection
    
    try:
        config = get_config()
        db_connection = DatabaseConnection(db_path=config.database.db_path)
        return ChunkMetadataStore(db_connection=db_connection)
    except Exception as e:
        logger.error(f"Failed to initialize ChunkMetadataStore: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service initialization failed: {str(e)}"
        )


async def get_correlation_id(
    x_correlation_id: Optional[str] = Header(None)
) -> str:
    """
    Get or generate correlation ID for request tracing.
    
    Args:
        x_correlation_id: Optional correlation ID from request header.
    
    Returns:
        Correlation ID string.
    """
    return x_correlation_id or str(uuid.uuid4())


# ============================================================================
# Helper Functions
# ============================================================================

def create_error_response(
    error_type: str,
    detail: str,
    correlation_id: str
) -> ErrorResponse:
    """
    Create a standardized error response.
    
    Args:
        error_type: Type of error (e.g., "NotFound", "ValidationError").
        detail: Detailed error message.
        correlation_id: Request correlation ID.
    
    Returns:
        ErrorResponse model instance.
    """
    return ErrorResponse(
        error=error_type,
        detail=detail,
        correlation_id=correlation_id,
        timestamp=datetime.now().isoformat()
    )


# ============================================================================
# Chunk Visibility Endpoints
# ============================================================================

@router.get(
    "/chunks/{file_id}",
    response_model=PaginatedChunkResponse,
    responses={
        404: {"model": ErrorResponse, "description": "File not found"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get all chunks for a file",
    description="Returns all chunks associated with a file including chunk text, "
                "row range, chunk index, and extraction strategy. Supports pagination."
)
async def get_chunks_for_file(
    file_id: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Number of items per page (max 100)"
    ),
    chunk_viewer: ChunkViewer = Depends(get_chunk_viewer),
    correlation_id: str = Depends(get_correlation_id)
) -> PaginatedChunkResponse:
    """
    Get all chunks for a file with pagination.
    
    Returns chunks including chunk text, row range, chunk index, extraction strategy,
    embedding metadata (vector dimensions, token count, model), and chunk boundaries.
    
    Requirements: 13.1, 13.5, 13.6
    
    Args:
        file_id: Unique identifier of the file.
        page: Page number (1-indexed).
        page_size: Number of items per page (default 20, max 100).
        chunk_viewer: Injected ChunkViewer service.
        correlation_id: Request correlation ID for tracing.
    
    Returns:
        PaginatedChunkResponse with chunks and pagination metadata.
    
    Raises:
        HTTPException: If file not found or retrieval fails.
    """
    logger.info(
        f"GET /chunks/{file_id} - page={page}, page_size={page_size}, "
        f"correlation_id={correlation_id}"
    )
    
    try:
        response = chunk_viewer.get_chunks_for_file(
            file_id=file_id,
            page=page,
            page_size=page_size
        )
        
        if response.total_count == 0:
            logger.warning(f"No chunks found for file {file_id}")
        
        return response
        
    except ChunkViewerError as e:
        logger.error(
            f"ChunkViewerError getting chunks for file {file_id}: {e}",
            extra={"correlation_id": correlation_id}
        )
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/chunks/{file_id}/sheets/{sheet_name}",
    response_model=PaginatedChunkResponse,
    responses={
        404: {"model": ErrorResponse, "description": "File or sheet not found"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get chunks for a specific sheet",
    description="Returns chunks for a specific sheet within a file. "
                "Supports pagination and additional filtering."
)
async def get_chunks_for_sheet(
    file_id: str,
    sheet_name: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Number of items per page (max 100)"
    ),
    chunk_viewer: ChunkViewer = Depends(get_chunk_viewer),
    correlation_id: str = Depends(get_correlation_id)
) -> PaginatedChunkResponse:
    """
    Get chunks for a specific sheet within a file.
    
    Filters results to only show chunks from the specified sheet.
    
    Requirements: 13.2, 13.5, 13.6
    
    Args:
        file_id: Unique identifier of the file.
        sheet_name: Name of the sheet to filter by.
        page: Page number (1-indexed).
        page_size: Number of items per page (default 20, max 100).
        chunk_viewer: Injected ChunkViewer service.
        correlation_id: Request correlation ID for tracing.
    
    Returns:
        PaginatedChunkResponse with chunks and pagination metadata.
    
    Raises:
        HTTPException: If file/sheet not found or retrieval fails.
    """
    logger.info(
        f"GET /chunks/{file_id}/sheets/{sheet_name} - page={page}, "
        f"page_size={page_size}, correlation_id={correlation_id}"
    )
    
    try:
        response = chunk_viewer.get_chunks_for_sheet(
            file_id=file_id,
            sheet_name=sheet_name,
            page=page,
            page_size=page_size
        )
        
        if response.total_count == 0:
            logger.warning(
                f"No chunks found for sheet {sheet_name} in file {file_id}"
            )
        
        return response
        
    except ChunkViewerError as e:
        logger.error(
            f"ChunkViewerError getting chunks for sheet: {e}",
            extra={"correlation_id": correlation_id}
        )
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/chunks/search",
    response_model=PaginatedChunkResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Search chunks with semantic similarity",
    description="Search chunks using semantic similarity matching. "
                "Supports filtering by extraction strategy, file, sheet, and content type. "
                "Returns chunks ordered by similarity score."
)
async def search_chunks(
    request: ChunkSearchRequest,
    chunk_viewer: ChunkViewer = Depends(get_chunk_viewer),
    correlation_id: str = Depends(get_correlation_id)
) -> PaginatedChunkResponse:
    """
    Search chunks with semantic similarity and optional filters.
    
    Performs semantic search using embeddings and combines results with
    metadata filtering. Filters are combined using AND logic.
    
    Requirements: 13.3, 13.5, 13.6
    
    Args:
        request: ChunkSearchRequest with query and optional filters.
        chunk_viewer: Injected ChunkViewer service.
        correlation_id: Request correlation ID for tracing.
    
    Returns:
        PaginatedChunkResponse with chunks including similarity_score.
    
    Raises:
        HTTPException: If search fails or query is invalid.
    """
    logger.info(
        f"POST /chunks/search - query='{request.query[:50]}...', "
        f"page={request.page}, correlation_id={correlation_id}"
    )
    
    try:
        # Build filters from request
        filters = ChunkFilters(
            extraction_strategy=request.extraction_strategy,
            file_id=request.file_id,
            sheet_name=request.sheet_name,
            content_type=request.content_type,
            min_quality_score=request.min_quality_score
        )
        
        response = chunk_viewer.search_chunks(
            query=request.query,
            filters=filters if not filters.is_empty() else None,
            page=request.page,
            page_size=request.page_size
        )
        
        if response.total_count == 0:
            logger.info(f"No chunks found matching search query")
        
        return response
        
    except ChunkViewerError as e:
        logger.error(
            f"ChunkViewerError searching chunks: {e}",
            extra={"correlation_id": correlation_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except ValueError as e:
        logger.warning(f"Invalid search request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# Extraction Metadata Endpoints
# ============================================================================

@router.get(
    "/files/{file_id}/extraction-metadata",
    response_model=ExtractionMetadataResponse,
    responses={
        404: {"model": ErrorResponse, "description": "File not found"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get extraction metadata for a file",
    description="Returns extraction details including strategy used, quality metrics, "
                "errors, warnings, and timing information."
)
async def get_extraction_metadata(
    file_id: str,
    chunk_viewer: ChunkViewer = Depends(get_chunk_viewer),
    correlation_id: str = Depends(get_correlation_id)
) -> ExtractionMetadataResponse:
    """
    Get extraction metadata for a file.
    
    Returns details about the extraction process including strategy used,
    quality scores, errors, warnings, and timing.
    
    Requirements: 13.4, 13.5
    
    Args:
        file_id: Unique identifier of the file.
        chunk_viewer: Injected ChunkViewer service.
        correlation_id: Request correlation ID for tracing.
    
    Returns:
        ExtractionMetadataResponse with extraction details.
    
    Raises:
        HTTPException: If file not found or retrieval fails.
    """
    logger.info(
        f"GET /files/{file_id}/extraction-metadata - "
        f"correlation_id={correlation_id}"
    )
    
    try:
        metadata = chunk_viewer.get_extraction_metadata(file_id=file_id)
        
        return ExtractionMetadataResponse(
            file_id=metadata.file_id,
            strategy_used=metadata.strategy_used,
            strategy_selected_reason=metadata.strategy_selected_reason,
            complexity_score=metadata.complexity_score,
            quality_score=metadata.quality_score,
            has_headers=metadata.has_headers,
            has_data=metadata.has_data,
            data_completeness=metadata.data_completeness,
            structure_clarity=metadata.structure_clarity,
            extraction_errors=metadata.extraction_errors,
            extraction_warnings=metadata.extraction_warnings,
            fallback_used=metadata.fallback_used,
            fallback_reason=metadata.fallback_reason,
            extraction_duration_ms=metadata.extraction_duration_ms,
            extracted_at=metadata.extracted_at
        )
        
    except ChunkViewerError as e:
        logger.error(
            f"ChunkViewerError getting extraction metadata: {e}",
            extra={"correlation_id": correlation_id}
        )
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# Version History Endpoints
# ============================================================================

@router.get(
    "/chunks/{file_id}/versions",
    response_model=VersionHistoryResponse,
    responses={
        404: {"model": ErrorResponse, "description": "File not found"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get version history for file chunks",
    description="Returns version history for all chunks in a file, "
                "showing changes across re-indexing events."
)
async def get_chunk_versions(
    file_id: str,
    chunk_id: Optional[str] = Query(
        None,
        description="Optional specific chunk ID to get versions for"
    ),
    version_store: ChunkVersionStore = Depends(get_chunk_version_store),
    correlation_id: str = Depends(get_correlation_id)
) -> VersionHistoryResponse:
    """
    Get version history for chunks in a file.
    
    Returns version records showing how chunks have changed across
    re-indexing events. Optionally filter to a specific chunk.
    
    Requirements: 21.2, 13.5, 13.6
    
    Args:
        file_id: Unique identifier of the file.
        chunk_id: Optional specific chunk ID to filter by.
        version_store: Injected ChunkVersionStore service.
        correlation_id: Request correlation ID for tracing.
    
    Returns:
        VersionHistoryResponse with version records.
    
    Raises:
        HTTPException: If file not found or retrieval fails.
    """
    logger.info(
        f"GET /chunks/{file_id}/versions - chunk_id={chunk_id}, "
        f"correlation_id={correlation_id}"
    )
    
    try:
        if chunk_id:
            # Get versions for specific chunk
            versions = version_store.get_version_history(chunk_id)
            version_dicts = [
                {
                    "version_id": v.version_id,
                    "chunk_id": v.chunk_id,
                    "version_number": v.version_number,
                    "chunk_text": v.chunk_text,
                    "extraction_strategy": v.extraction_strategy,
                    "indexed_at": v.indexed_at.isoformat(),
                    "change_summary": v.change_summary,
                }
                for v in versions
            ]
        else:
            # Get all versions for file
            version_dicts = version_store.get_versions_for_file(file_id)
        
        return VersionHistoryResponse(
            file_id=file_id,
            versions=version_dicts,
            total_count=len(version_dicts)
        )
        
    except ChunkViewerError as e:
        logger.error(
            f"ChunkViewerError getting chunk versions: {e}",
            extra={"correlation_id": correlation_id}
        )
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# Feedback Endpoints
# ============================================================================

@router.post(
    "/chunks/{chunk_id}/feedback",
    response_model=FeedbackSubmitResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid feedback data"},
        404: {"model": ErrorResponse, "description": "Chunk not found"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Submit chunk quality feedback",
    description="Submit feedback for a chunk including quality rating and comments. "
                "Chunks with multiple negative reports are flagged for review."
)
async def submit_chunk_feedback(
    chunk_id: str,
    request: FeedbackSubmitRequest,
    feedback_collector: FeedbackCollector = Depends(get_feedback_collector),
    correlation_id: str = Depends(get_correlation_id)
) -> FeedbackSubmitResponse:
    """
    Submit feedback for a chunk.
    
    Accepts quality ratings and comments. If a chunk receives multiple
    negative reports (rating <= 2), it will be flagged for review.
    
    Requirements: 27.1, 13.5
    
    Args:
        chunk_id: Unique identifier of the chunk.
        request: FeedbackSubmitRequest with feedback details.
        feedback_collector: Injected FeedbackCollector service.
        correlation_id: Request correlation ID for tracing.
    
    Returns:
        FeedbackSubmitResponse confirming submission.
    
    Raises:
        HTTPException: If validation fails or submission fails.
    """
    logger.info(
        f"POST /chunks/{chunk_id}/feedback - type={request.feedback_type}, "
        f"rating={request.rating}, correlation_id={correlation_id}"
    )
    
    try:
        feedback_record = feedback_collector.submit_feedback(
            chunk_id=chunk_id,
            feedback_type=request.feedback_type,
            rating=request.rating,
            comment=request.comment,
            user_id=request.user_id
        )
        
        return FeedbackSubmitResponse(
            feedback_id=feedback_record.feedback_id,
            chunk_id=feedback_record.chunk_id,
            feedback_type=feedback_record.feedback_type,
            rating=feedback_record.rating,
            created_at=feedback_record.created_at.isoformat(),
            message="Feedback submitted successfully"
        )
        
    except ChunkViewerError as e:
        logger.error(
            f"ChunkViewerError submitting feedback: {e}",
            extra={"correlation_id": correlation_id}
        )
        error_msg = str(e).lower()
        if "invalid feedback type" in error_msg or "rating must be" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except ValueError as e:
        logger.warning(f"Invalid feedback request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/chunks/feedback-summary",
    response_model=FeedbackSummaryResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get aggregated feedback statistics",
    description="Returns aggregated feedback statistics across all chunks, "
                "including counts by type, average ratings, and flagged chunks."
)
async def get_feedback_summary(
    feedback_collector: FeedbackCollector = Depends(get_feedback_collector),
    correlation_id: str = Depends(get_correlation_id)
) -> FeedbackSummaryResponse:
    """
    Get aggregated feedback statistics.
    
    Returns overall statistics including total feedback count, average rating,
    feedback by type, and chunks flagged for review.
    
    Requirements: 27.4, 13.5
    
    Args:
        feedback_collector: Injected FeedbackCollector service.
        correlation_id: Request correlation ID for tracing.
    
    Returns:
        FeedbackSummaryResponse with aggregated statistics.
    
    Raises:
        HTTPException: If aggregation fails.
    """
    logger.info(
        f"GET /chunks/feedback-summary - correlation_id={correlation_id}"
    )
    
    try:
        summary = feedback_collector.get_feedback_summary()
        
        return FeedbackSummaryResponse(
            total_feedback_count=summary["total_feedback_count"],
            total_chunks_with_feedback=summary["total_chunks_with_feedback"],
            average_rating=summary["average_rating"],
            feedback_by_type=summary["feedback_by_type"],
            chunks_flagged_for_review=summary["chunks_flagged_for_review"],
            top_problematic_chunks=summary["top_problematic_chunks"],
            generated_at=summary["generated_at"]
        )
        
    except ChunkViewerError as e:
        logger.error(
            f"ChunkViewerError getting feedback summary: {e}",
            extra={"correlation_id": correlation_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# Quality Report Endpoints
# ============================================================================

@router.get(
    "/files/quality-report",
    response_model=QualityReportResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get quality scores for all indexed files",
    description="Returns quality scores and extraction metadata for all indexed files. "
                "Files with quality score below 0.5 are flagged as problematic."
)
async def get_quality_report(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Number of items per page (max 100)"
    ),
    min_quality_score: Optional[float] = Query(
        None,
        ge=0.0,
        le=1.0,
        description="Filter by minimum quality score"
    ),
    problematic_only: bool = Query(
        False,
        description="Only return files with quality score < 0.5"
    ),
    metadata_store: ChunkMetadataStore = Depends(get_metadata_store),
    correlation_id: str = Depends(get_correlation_id)
) -> QualityReportResponse:
    """
    Get quality scores for all indexed files.
    
    Returns quality metrics for all files including quality score,
    data completeness, structure clarity, and extraction strategy.
    Files with quality score below 0.5 are flagged as problematic.
    
    Requirements: 22.5, 13.5, 13.6
    
    Args:
        page: Page number (1-indexed).
        page_size: Number of items per page (default 20, max 100).
        min_quality_score: Optional minimum quality score filter.
        problematic_only: If True, only return files with quality < 0.5.
        metadata_store: Injected ChunkMetadataStore service.
        correlation_id: Request correlation ID for tracing.
    
    Returns:
        QualityReportResponse with file quality data.
    
    Raises:
        HTTPException: If retrieval fails.
    """
    logger.info(
        f"GET /files/quality-report - page={page}, page_size={page_size}, "
        f"problematic_only={problematic_only}, correlation_id={correlation_id}"
    )
    
    try:
        # Query extraction metadata for all files
        from src.config import get_config
        from src.database.connection import DatabaseConnection
        
        config = get_config()
        db_connection = DatabaseConnection(db_path=config.database.db_path)
        
        # Build query with filters
        where_clauses = []
        params: List[Any] = []
        
        if problematic_only:
            where_clauses.append("em.quality_score < 0.5")
        elif min_quality_score is not None:
            where_clauses.append("em.quality_score >= ?")
            params.append(min_quality_score)
        
        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*) as total
            FROM extraction_metadata em
            WHERE {where_clause}
        """
        count_result = db_connection.execute_query(count_query, tuple(params))
        total_count = count_result[0]["total"] if count_result else 0
        
        # Get paginated results
        offset = (page - 1) * page_size
        data_query = f"""
            SELECT 
                em.file_id,
                f.name as file_name,
                em.quality_score,
                em.has_headers,
                em.has_data,
                em.data_completeness,
                em.structure_clarity,
                em.strategy_used,
                em.extracted_at
            FROM extraction_metadata em
            LEFT JOIN files f ON em.file_id = f.file_id
            WHERE {where_clause}
            ORDER BY em.quality_score ASC
            LIMIT ? OFFSET ?
        """
        
        data_params = tuple(params) + (page_size, offset)
        results = db_connection.execute_query(data_query, data_params)
        
        # Build file quality reports
        files: List[FileQualityReport] = []
        total_quality = 0.0
        problematic_count = 0
        
        for row in results:
            row_dict = dict(row)
            quality_score = row_dict.get("quality_score", 0.0)
            is_problematic = quality_score < 0.5
            
            if is_problematic:
                problematic_count += 1
            
            total_quality += quality_score
            
            files.append(FileQualityReport(
                file_id=row_dict["file_id"],
                file_name=row_dict.get("file_name"),
                quality_score=quality_score,
                has_headers=bool(row_dict.get("has_headers")),
                has_data=bool(row_dict.get("has_data")),
                data_completeness=row_dict.get("data_completeness", 0.0),
                structure_clarity=row_dict.get("structure_clarity", 0.0),
                extraction_strategy=row_dict.get("strategy_used", "unknown"),
                is_problematic=is_problematic,
                extracted_at=row_dict.get("extracted_at", "")
            ))
        
        # Calculate average quality score
        avg_quality = total_quality / len(files) if files else 0.0
        
        has_more = (offset + len(files)) < total_count
        
        return QualityReportResponse(
            files=files,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_more=has_more,
            average_quality_score=round(avg_quality, 3),
            problematic_files_count=problematic_count
        )
        
    except Exception as e:
        logger.error(
            f"Error getting quality report: {e}",
            extra={"correlation_id": correlation_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate quality report: {str(e)}"
        )
