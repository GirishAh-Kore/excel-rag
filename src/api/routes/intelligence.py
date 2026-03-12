"""
Intelligence API Routes

This module provides API endpoints for intelligent features including
query suggestions, anomaly detection, and usage statistics.

Endpoints:
- GET /api/v1/query/suggestions - Get query suggestions
- GET /api/v1/files/{file_id}/anomalies - Get detected anomalies
- GET /api/v1/usage/summary - Get query cost statistics

Requirements: 37.1, 38.5, 42.4
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.exceptions import RAGSystemError
from src.intelligence.anomaly_detector import AnomalySeverity, AnomalyType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["intelligence"])


# ============================================================================
# Request/Response Models
# ============================================================================


class QuerySuggestion(BaseModel):
    """A single query suggestion."""
    suggestion: str = Field(..., description="Suggested query text")
    category: str = Field(..., description="Category: aggregation, lookup, etc.")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the suggestion"
    )
    based_on: Optional[str] = Field(
        default=None,
        description="What the suggestion is based on"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "suggestion": "What is the total revenue for Q1 2024?",
                "category": "aggregation",
                "confidence": 0.85,
                "based_on": "file_content"
            }
        }


class SuggestionsResponse(BaseModel):
    """Response model for query suggestions."""
    suggestions: list[QuerySuggestion]
    file_context: Optional[str] = Field(
        default=None,
        description="File ID used for context"
    )
    generated_at: str

    class Config:
        json_schema_extra = {
            "example": {
                "suggestions": [
                    {
                        "suggestion": "What is the total revenue?",
                        "category": "aggregation",
                        "confidence": 0.9,
                        "based_on": "column_headers"
                    }
                ],
                "file_context": "file_123",
                "generated_at": "2024-01-15T10:30:00Z"
            }
        }


class DetectedAnomalyResponse(BaseModel):
    """Response model for a detected anomaly."""
    anomaly_type: str = Field(..., description="Type of anomaly detected")
    severity: str = Field(..., description="Severity level: low, medium, high, critical")
    location: str = Field(..., description="Location of the anomaly")
    value: Any = Field(..., description="The anomalous value")
    expected: Optional[str] = Field(default=None, description="Expected value or range")
    message: str = Field(..., description="Human-readable description")

    class Config:
        json_schema_extra = {
            "example": {
                "anomaly_type": "numeric_outlier_iqr",
                "severity": "high",
                "location": "Revenue[42]",
                "value": 999999999,
                "expected": "[10000, 500000]",
                "message": "Value 999999999 is outside IQR bounds"
            }
        }


class AnomalyReportResponse(BaseModel):
    """Response model for anomaly detection report."""
    file_id: str
    total_rows: int
    total_columns: int
    anomaly_count: int
    has_critical: bool
    anomalies: list[DetectedAnomalyResponse]
    summary: dict[str, int] = Field(
        default_factory=dict,
        description="Count of anomalies by type"
    )
    analyzed_at: str

    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "file_123",
                "total_rows": 1000,
                "total_columns": 10,
                "anomaly_count": 5,
                "has_critical": False,
                "anomalies": [],
                "summary": {"numeric_outlier_iqr": 3, "missing_value": 2},
                "analyzed_at": "2024-01-15T10:30:00Z"
            }
        }


class UsageStatistics(BaseModel):
    """Usage statistics for a time period."""
    total_queries: int = Field(..., description="Total queries processed")
    total_cost_units: float = Field(..., description="Total cost units consumed")
    average_cost_per_query: float = Field(..., description="Average cost per query")
    queries_by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Query count by type"
    )
    peak_usage_hour: Optional[int] = Field(
        default=None,
        description="Hour with most queries (0-23)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_queries": 1500,
                "total_cost_units": 750.5,
                "average_cost_per_query": 0.5,
                "queries_by_type": {
                    "aggregation": 600,
                    "lookup": 400,
                    "summarization": 300,
                    "comparison": 200
                },
                "peak_usage_hour": 14
            }
        }


class UsageSummaryResponse(BaseModel):
    """Response model for usage summary."""
    period_start: str
    period_end: str
    statistics: UsageStatistics
    cost_limit: Optional[float] = Field(
        default=None,
        description="Configured cost limit"
    )
    cost_limit_remaining: Optional[float] = Field(
        default=None,
        description="Remaining cost units before limit"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "period_start": "2024-01-01T00:00:00Z",
                "period_end": "2024-01-31T23:59:59Z",
                "statistics": {
                    "total_queries": 1500,
                    "total_cost_units": 750.5,
                    "average_cost_per_query": 0.5,
                    "queries_by_type": {},
                    "peak_usage_hour": 14
                },
                "cost_limit": 1000.0,
                "cost_limit_remaining": 249.5
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


def get_anomaly_detector():
    """Get AnomalyDetector instance."""
    from src.intelligence.anomaly_detector import AnomalyDetector, AnomalyDetectorConfig
    
    try:
        return AnomalyDetector(config=AnomalyDetectorConfig())
    except Exception as e:
        logger.error(f"Failed to initialize AnomalyDetector: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service initialization failed: {str(e)}"
        )


def get_chunk_metadata_store():
    """Get ChunkMetadataStore for file data access."""
    from src.chunk_viewer.metadata_store import ChunkMetadataStore
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


def get_cost_estimator():
    """Get QueryCostEstimator instance."""
    from src.config import get_config
    from src.database.connection import DatabaseConnection
    from src.query_pipeline.cost_estimator import QueryCostEstimator, CostEstimatorConfig
    
    try:
        config = get_config()
        db_connection = DatabaseConnection(db_path=config.database.db_path)
        return QueryCostEstimator(
            db_connection=db_connection,
            config=CostEstimatorConfig(),
        )
    except Exception as e:
        logger.error(f"Failed to initialize QueryCostEstimator: {e}", exc_info=True)
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
# Intelligence Endpoints
# ============================================================================


@router.get(
    "/query/suggestions",
    response_model=SuggestionsResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get query suggestions",
    description="Get intelligent query suggestions based on indexed file content "
                "and common query patterns."
)
async def get_query_suggestions(
    file_id: Optional[str] = Query(
        None,
        description="Optional file ID to generate context-aware suggestions"
    ),
    limit: int = Query(
        5,
        ge=1,
        le=20,
        description="Maximum number of suggestions to return"
    ),
    metadata_store=Depends(get_chunk_metadata_store),
    correlation_id: str = Depends(get_correlation_id)
) -> SuggestionsResponse:
    """
    Get query suggestions based on file content and patterns.
    
    Requirements: 37.1
    """
    logger.info(
        f"GET /query/suggestions - file_id={file_id}, limit={limit}, "
        f"correlation_id={correlation_id}"
    )
    
    suggestions: list[QuerySuggestion] = []
    
    try:
        # Generate suggestions based on file content if file_id provided
        if file_id:
            # Get file metadata to understand content
            chunks = metadata_store.get_chunks_for_file(file_id, page=1, page_size=5)
            
            if chunks:
                # Analyze chunk content for suggestion generation
                column_names = set()
                for chunk in chunks:
                    if hasattr(chunk, 'metadata') and chunk.metadata:
                        cols = chunk.metadata.get('columns', [])
                        column_names.update(cols)
                
                # Generate aggregation suggestions for numeric-looking columns
                numeric_indicators = ['revenue', 'sales', 'amount', 'total', 'count', 'price', 'cost']
                for col in column_names:
                    col_lower = col.lower()
                    if any(ind in col_lower for ind in numeric_indicators):
                        suggestions.append(QuerySuggestion(
                            suggestion=f"What is the total {col}?",
                            category="aggregation",
                            confidence=0.85,
                            based_on="column_headers",
                        ))
                        if len(suggestions) >= limit:
                            break
        
        # Add default suggestions if we don't have enough
        default_suggestions = [
            QuerySuggestion(
                suggestion="Show me a summary of the data",
                category="summarization",
                confidence=0.7,
                based_on="common_pattern",
            ),
            QuerySuggestion(
                suggestion="What are the top 10 values?",
                category="lookup",
                confidence=0.65,
                based_on="common_pattern",
            ),
            QuerySuggestion(
                suggestion="Compare this month to last month",
                category="comparison",
                confidence=0.6,
                based_on="common_pattern",
            ),
        ]
        
        for default in default_suggestions:
            if len(suggestions) >= limit:
                break
            suggestions.append(default)
        
        return SuggestionsResponse(
            suggestions=suggestions[:limit],
            file_context=file_id,
            generated_at=datetime.utcnow().isoformat(),
        )
        
    except Exception as e:
        logger.error(
            f"Error generating suggestions: {e}",
            extra={"correlation_id": correlation_id}
        )
        # Return default suggestions on error
        return SuggestionsResponse(
            suggestions=[
                QuerySuggestion(
                    suggestion="Show me a summary of the data",
                    category="summarization",
                    confidence=0.5,
                    based_on="fallback",
                )
            ],
            file_context=file_id,
            generated_at=datetime.utcnow().isoformat(),
        )



@router.get(
    "/files/{file_id}/anomalies",
    response_model=AnomalyReportResponse,
    responses={
        404: {"model": ErrorResponse, "description": "File not found"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get detected anomalies",
    description="Analyze a file for anomalies including numeric outliers, "
                "missing values, duplicates, and formatting inconsistencies."
)
async def get_file_anomalies(
    file_id: str,
    anomaly_detector=Depends(get_anomaly_detector),
    metadata_store=Depends(get_chunk_metadata_store),
    correlation_id: str = Depends(get_correlation_id)
) -> AnomalyReportResponse:
    """
    Detect anomalies in a file's data.
    
    Requirements: 38.5
    """
    logger.info(
        f"GET /files/{file_id}/anomalies - correlation_id={correlation_id}"
    )
    
    try:
        # Get file chunks to analyze
        chunks = metadata_store.get_chunks_for_file(file_id, page=1, page_size=100)
        
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found or has no indexed data: {file_id}"
            )
        
        # Extract data from chunks for analysis
        data: list[list[Any]] = []
        column_names: list[str] = []
        
        for chunk in chunks:
            # Parse chunk text into rows
            if hasattr(chunk, 'chunk_text') and chunk.chunk_text:
                lines = chunk.chunk_text.strip().split('\n')
                for line in lines:
                    # Simple CSV-like parsing
                    row = [cell.strip() for cell in line.split(',')]
                    if row and any(cell for cell in row):
                        data.append(row)
            
            # Extract column names from metadata
            if hasattr(chunk, 'metadata') and chunk.metadata:
                cols = chunk.metadata.get('columns', [])
                if cols and not column_names:
                    column_names = cols
        
        # Run anomaly detection
        report = anomaly_detector.analyze(
            data=data,
            column_names=column_names if column_names else None,
        )
        
        # Convert anomalies to response format
        anomaly_responses = [
            DetectedAnomalyResponse(
                anomaly_type=a.anomaly_type.value,
                severity=a.severity.value,
                location=a.location,
                value=a.value,
                expected=a.expected,
                message=a.message,
            )
            for a in report.anomalies
        ]
        
        return AnomalyReportResponse(
            file_id=file_id,
            total_rows=report.total_rows,
            total_columns=report.total_columns,
            anomaly_count=report.anomaly_count,
            has_critical=report.has_critical,
            anomalies=anomaly_responses,
            summary=report.summary,
            analyzed_at=report.analyzed_at.isoformat(),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error detecting anomalies: {e}",
            extra={"correlation_id": correlation_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection failed: {str(e)}"
        )


@router.get(
    "/usage/summary",
    response_model=UsageSummaryResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get usage summary",
    description="Get query cost statistics and usage summary for the specified period."
)
async def get_usage_summary(
    days: int = Query(
        30,
        ge=1,
        le=365,
        description="Number of days to include in summary"
    ),
    cost_estimator=Depends(get_cost_estimator),
    correlation_id: str = Depends(get_correlation_id)
) -> UsageSummaryResponse:
    """
    Get query cost statistics and usage summary.
    
    Requirements: 42.4
    """
    from datetime import timedelta
    
    logger.info(
        f"GET /usage/summary - days={days}, correlation_id={correlation_id}"
    )
    
    try:
        now = datetime.utcnow()
        period_start = now - timedelta(days=days)
        
        # Get usage statistics from cost estimator
        stats = cost_estimator.get_usage_statistics(
            start_date=period_start,
            end_date=now,
        )
        
        # Get cost limit configuration
        cost_limit = cost_estimator.get_cost_limit()
        cost_remaining = None
        if cost_limit is not None:
            cost_remaining = max(0, cost_limit - stats.get('total_cost_units', 0))
        
        return UsageSummaryResponse(
            period_start=period_start.isoformat(),
            period_end=now.isoformat(),
            statistics=UsageStatistics(
                total_queries=stats.get('total_queries', 0),
                total_cost_units=stats.get('total_cost_units', 0.0),
                average_cost_per_query=stats.get('average_cost_per_query', 0.0),
                queries_by_type=stats.get('queries_by_type', {}),
                peak_usage_hour=stats.get('peak_usage_hour'),
            ),
            cost_limit=cost_limit,
            cost_limit_remaining=cost_remaining,
        )
        
    except Exception as e:
        logger.error(
            f"Error getting usage summary: {e}",
            extra={"correlation_id": correlation_id}
        )
        # Return empty statistics on error
        now = datetime.utcnow()
        return UsageSummaryResponse(
            period_start=(now - timedelta(days=days)).isoformat(),
            period_end=now.isoformat(),
            statistics=UsageStatistics(
                total_queries=0,
                total_cost_units=0.0,
                average_cost_per_query=0.0,
                queries_by_type={},
                peak_usage_hour=None,
            ),
            cost_limit=None,
            cost_limit_remaining=None,
        )
