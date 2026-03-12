"""
Export and Webhook API Routes

This module provides API endpoints for exporting query results and
managing webhook registrations for event notifications.

Endpoints:
- POST /api/v1/export - Export results to CSV, Excel, or JSON
- POST /api/v1/webhooks - Register webhook URL
- GET /api/v1/webhooks/{webhook_id}/deliveries - Get delivery history

Requirements: 26.3, 28.2, 28.5
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.exceptions import ExportError, WebhookError
from src.export.service import ExportFormat
from src.models.enterprise import WebhookDelivery, WebhookRegistration

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["export", "webhooks"])


# ============================================================================
# Request/Response Models
# ============================================================================


class ExportRequest(BaseModel):
    """Request model for exporting data."""
    data: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="Data to export as list of dictionaries"
    )
    format: str = Field(
        default="csv",
        description="Export format: csv, xlsx, or json"
    )
    filename_prefix: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional prefix for the exported filename"
    )
    include_metadata: bool = Field(
        default=True,
        description="Whether to include metadata in the export"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {"name": "Product A", "revenue": 10000, "quarter": "Q1"},
                    {"name": "Product B", "revenue": 15000, "quarter": "Q1"}
                ],
                "format": "xlsx",
                "filename_prefix": "sales_report",
                "include_metadata": True
            }
        }


class ExportResponse(BaseModel):
    """Response model for export operation."""
    export_id: str = Field(..., description="Unique export identifier")
    format: str = Field(..., description="Export format used")
    filename: str = Field(..., description="Generated filename")
    row_count: int = Field(..., description="Number of rows exported")
    created_at: str = Field(..., description="Export timestamp")
    download_url: Optional[str] = Field(
        default=None,
        description="URL to download the exported file"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "export_id": "exp_abc123",
                "format": "xlsx",
                "filename": "sales_report_20240115_103000.xlsx",
                "row_count": 100,
                "created_at": "2024-01-15T10:30:00Z",
                "download_url": None
            }
        }


class WebhookRegisterRequest(BaseModel):
    """Request model for registering a webhook."""
    url: str = Field(
        ...,
        min_length=1,
        description="URL to receive webhook POST requests"
    )
    events: list[str] = Field(
        ...,
        min_length=1,
        description="Event types to subscribe to"
    )
    secret: Optional[str] = Field(
        default=None,
        description="Optional secret for signature verification"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/webhooks/excel-rag",
                "events": ["indexing_complete", "query_failed"],
                "secret": "whsec_abc123xyz"
            }
        }


class WebhookResponse(BaseModel):
    """Response model for webhook operations."""
    webhook_id: str
    url: str
    events: list[str]
    is_active: bool
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "webhook_id": "wh_abc123",
                "url": "https://example.com/webhooks/excel-rag",
                "events": ["indexing_complete", "query_failed"],
                "is_active": True,
                "message": "Webhook registered successfully"
            }
        }


class DeliveryResponse(BaseModel):
    """Response model for a single delivery record."""
    delivery_id: str
    event_type: str
    status: str
    attempts: int
    last_attempt_at: Optional[str]
    response_code: Optional[int]

    class Config:
        json_schema_extra = {
            "example": {
                "delivery_id": "del_abc123",
                "event_type": "indexing_complete",
                "status": "delivered",
                "attempts": 1,
                "last_attempt_at": "2024-01-15T10:35:00Z",
                "response_code": 200
            }
        }


class DeliveryHistoryResponse(BaseModel):
    """Response model for delivery history."""
    webhook_id: str
    deliveries: list[DeliveryResponse]
    total_count: int
    page: int
    page_size: int
    has_more: bool

    class Config:
        json_schema_extra = {
            "example": {
                "webhook_id": "wh_abc123",
                "deliveries": [],
                "total_count": 0,
                "page": 1,
                "page_size": 20,
                "has_more": False
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


def get_export_service():
    """Get ExportService instance with injected dependencies."""
    from src.config import get_config
    from src.database.connection import DatabaseConnection
    from src.export.service import ExportService, ExportServiceConfig
    from src.export.store import SQLiteExportStore
    
    try:
        config = get_config()
        db_connection = DatabaseConnection(db_path=config.database.db_path)
        export_store = SQLiteExportStore(db_connection=db_connection)
        
        return ExportService(
            export_store=export_store,
            config=ExportServiceConfig(),
        )
    except Exception as e:
        logger.error(f"Failed to initialize ExportService: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service initialization failed: {str(e)}"
        )


def get_webhook_manager():
    """Get WebhookManager instance with injected dependencies."""
    from src.config import get_config
    from src.database.connection import DatabaseConnection
    from src.webhooks.manager import WebhookManager
    from src.webhooks.store import SQLiteWebhookStore
    
    try:
        config = get_config()
        db_connection = DatabaseConnection(db_path=config.database.db_path)
        webhook_store = SQLiteWebhookStore(db_connection=db_connection)
        
        return WebhookManager(webhook_store=webhook_store)
    except Exception as e:
        logger.error(f"Failed to initialize WebhookManager: {e}", exc_info=True)
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
# Export Endpoints
# ============================================================================


@router.post(
    "/export",
    responses={
        200: {"description": "Export successful, returns file content"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Export data to file",
    description="Export data to CSV, Excel (.xlsx), or JSON format. "
                "Returns the file content directly for download."
)
async def export_data(
    request: ExportRequest,
    export_service=Depends(get_export_service),
    correlation_id: str = Depends(get_correlation_id)
) -> Response:
    """
    Export data to the specified format.
    
    Returns the exported file content directly as a downloadable response.
    
    Requirements: 26.3
    """
    logger.info(
        f"POST /export - format={request.format}, rows={len(request.data)}, "
        f"correlation_id={correlation_id}"
    )
    
    # Validate and convert format
    try:
        export_format = ExportFormat(request.format.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format '{request.format}'. "
                   f"Supported formats: csv, xlsx, json"
        )
    
    try:
        result = export_service.export_data(
            data=request.data,
            format=export_format,
            filename_prefix=request.filename_prefix,
            include_metadata=request.include_metadata,
        )
        
        # Determine content type
        content_type_map = {
            ExportFormat.CSV: "text/csv",
            ExportFormat.EXCEL: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ExportFormat.JSON: "application/json",
        }
        content_type = content_type_map.get(export_format, "application/octet-stream")
        
        return Response(
            content=result.data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{result.filename}"',
                "X-Export-Id": result.export_id,
                "X-Row-Count": str(result.row_count),
                "X-Correlation-Id": correlation_id,
            }
        )
        
    except ExportError as e:
        logger.error(
            f"ExportError: {e}",
            extra={"correlation_id": correlation_id}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )



# ============================================================================
# Webhook Endpoints
# ============================================================================


@router.post(
    "/webhooks",
    response_model=WebhookResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Register webhook",
    description="Register a webhook URL to receive event notifications. "
                "Supported events: indexing_complete, query_failed, "
                "low_confidence_answer, batch_complete."
)
async def register_webhook(
    request: WebhookRegisterRequest,
    webhook_manager=Depends(get_webhook_manager),
    correlation_id: str = Depends(get_correlation_id)
) -> WebhookResponse:
    """
    Register a new webhook for event notifications.
    
    Requirements: 28.2
    """
    logger.info(
        f"POST /webhooks - url={request.url}, events={request.events}, "
        f"correlation_id={correlation_id}"
    )
    
    try:
        webhook = webhook_manager.register_webhook(
            url=request.url,
            events=request.events,
            secret=request.secret,
        )
        
        return WebhookResponse(
            webhook_id=webhook.webhook_id,
            url=webhook.url,
            events=webhook.events,
            is_active=webhook.is_active,
            message="Webhook registered successfully",
        )
        
    except WebhookError as e:
        logger.error(
            f"WebhookError registering webhook: {e}",
            extra={"correlation_id": correlation_id}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/webhooks/{webhook_id}/deliveries",
    response_model=DeliveryHistoryResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Webhook not found"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    },
    summary="Get webhook delivery history",
    description="Get the delivery history for a webhook, including status "
                "and retry information for each delivery attempt."
)
async def get_webhook_deliveries(
    webhook_id: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    webhook_manager=Depends(get_webhook_manager),
    correlation_id: str = Depends(get_correlation_id)
) -> DeliveryHistoryResponse:
    """
    Get delivery history for a webhook.
    
    Requirements: 28.5
    """
    logger.info(
        f"GET /webhooks/{webhook_id}/deliveries - page={page}, "
        f"page_size={page_size}, correlation_id={correlation_id}"
    )
    
    try:
        history = webhook_manager.get_delivery_history(
            webhook_id=webhook_id,
            page=page,
            page_size=page_size,
        )
        
        delivery_responses = [
            DeliveryResponse(
                delivery_id=d.delivery_id,
                event_type=d.event_type,
                status=d.status,
                attempts=d.attempts,
                last_attempt_at=d.last_attempt_at.isoformat() if d.last_attempt_at else None,
                response_code=d.response_code,
            )
            for d in history.deliveries
        ]
        
        return DeliveryHistoryResponse(
            webhook_id=history.webhook_id,
            deliveries=delivery_responses,
            total_count=history.total_count,
            page=history.page,
            page_size=history.page_size,
            has_more=history.has_more,
        )
        
    except WebhookError as e:
        logger.error(
            f"WebhookError getting deliveries: {e}",
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
