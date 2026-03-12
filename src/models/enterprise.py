"""
Enterprise data models for batch processing, templates, webhooks, and access control.

This module defines the data models used for enterprise features including:
- Batch query processing (BatchQueryRequest, BatchQueryStatus)
- Query templates (QueryTemplate)
- Webhook notifications (WebhookRegistration, WebhookDelivery)
- Access control (UserRole, AccessControlEntry, AccessAuditLog)

These models support Requirements 24.1, 25.1, 28.1, and 29.1.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class UserRole(str, Enum):
    """
    User roles for role-based access control.
    
    Defines the permission levels for accessing chunk details and
    other protected resources.
    
    Roles:
        ADMIN: Full access to all features and data.
        DEVELOPER: Access to debugging tools and chunk visibility.
        ANALYST: Access to query features and data analysis.
        VIEWER: Read-only access to query results.
    
    Supports Requirement 29.1: Enforce role-based access control with roles:
    admin, developer, analyst, and viewer.
    """
    ADMIN = "admin"
    DEVELOPER = "developer"
    ANALYST = "analyst"
    VIEWER = "viewer"


class BatchQueryRequest(BaseModel):
    """
    Request for batch query processing.
    
    Allows submitting multiple queries in a single request for efficient
    batch processing. Queries are processed in parallel where possible.
    
    Attributes:
        queries: List of natural language queries to process (max 100).
        file_hints: Optional list of file IDs or names to restrict search.
        sheet_hints: Optional list of sheet names to restrict search.
    
    Supports Requirement 24.1: Accept array of queries (max 100) for batch processing.
    """
    queries: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of natural language queries to process (max 100)"
    )
    file_hints: Optional[list[str]] = Field(
        default=None,
        description="Optional file IDs or names to restrict search scope"
    )
    sheet_hints: Optional[list[str]] = Field(
        default=None,
        description="Optional sheet names to restrict search scope"
    )
    
    @field_validator('queries')
    @classmethod
    def validate_queries_not_empty(cls, v: list[str]) -> list[str]:
        """Validate that queries list contains non-empty strings."""
        for i, query in enumerate(v):
            if not query or not query.strip():
                raise ValueError(f"Query at index {i} cannot be empty")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "queries": [
                    "What is the total revenue for Q1 2024?",
                    "Show me the top 10 products by sales",
                    "Compare Q1 vs Q2 performance"
                ],
                "file_hints": ["sales_2024.xlsx"],
                "sheet_hints": None
            }
        }


class BatchQueryStatus(BaseModel):
    """
    Status of batch query processing.
    
    Tracks the progress and results of a batch query request,
    including individual query statuses and overall completion.
    
    Attributes:
        batch_id: Unique identifier for the batch request.
        total_queries: Total number of queries in the batch.
        completed: Number of queries successfully completed.
        failed: Number of queries that failed.
        status: Overall batch status (pending, processing, completed, partial).
        results: Optional list of query results when processing is complete.
    
    Supports Requirement 24.1: Batch query processing with status tracking.
    """
    batch_id: str = Field(
        ...,
        description="Unique identifier for the batch request"
    )
    total_queries: int = Field(
        ...,
        ge=1,
        le=100,
        description="Total number of queries in the batch"
    )
    completed: int = Field(
        ...,
        ge=0,
        description="Number of queries successfully completed"
    )
    failed: int = Field(
        ...,
        ge=0,
        description="Number of queries that failed"
    )
    status: str = Field(
        ...,
        description="Overall batch status: pending, processing, completed, partial"
    )
    results: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Query results when processing is complete"
    )
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is a valid value."""
        valid_statuses = {'pending', 'processing', 'completed', 'partial'}
        if v not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}, got '{v}'")
        return v
    
    def __init__(self, **data: Any) -> None:
        """Initialize and validate completed + failed <= total_queries."""
        super().__init__(**data)
        if self.completed + self.failed > self.total_queries:
            raise ValueError(
                f"completed ({self.completed}) + failed ({self.failed}) "
                f"cannot exceed total_queries ({self.total_queries})"
            )
    
    class Config:
        json_schema_extra = {
            "example": {
                "batch_id": "batch_abc123",
                "total_queries": 10,
                "completed": 8,
                "failed": 1,
                "status": "processing",
                "results": None
            }
        }


class QueryTemplate(BaseModel):
    """
    Parameterized query template for reusable queries.
    
    Allows users to create query templates with placeholders that can
    be filled in at execution time. Templates use {{parameter_name}} syntax.
    
    Attributes:
        template_id: Unique identifier for the template.
        name: Human-readable name for the template.
        template_text: Template text with {{parameter}} placeholders.
        parameters: List of parameter names extracted from template_text.
        created_by: User ID of the template creator.
        created_at: Timestamp when the template was created.
        is_shared: Whether the template is shared with other users.
    
    Supports Requirement 25.1: Create parameterized query templates.
    """
    template_id: str = Field(
        ...,
        description="Unique identifier for the template"
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable name for the template"
    )
    template_text: str = Field(
        ...,
        min_length=1,
        description="Template text with {{parameter}} placeholders"
    )
    parameters: list[str] = Field(
        default_factory=list,
        description="List of parameter names in the template"
    )
    created_by: str = Field(
        ...,
        description="User ID of the template creator"
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the template was created"
    )
    is_shared: bool = Field(
        default=False,
        description="Whether the template is shared with other users"
    )
    
    @field_validator('template_id', 'created_by')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v
    
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


# Valid webhook event types per Requirement 28.1
VALID_WEBHOOK_EVENTS = frozenset({
    "indexing_complete",
    "query_failed",
    "low_confidence_answer",
    "batch_complete"
})


class WebhookRegistration(BaseModel):
    """
    Webhook registration for event notifications.
    
    Allows users to register webhook URLs to receive notifications
    for specific events like indexing completion or query failures.
    
    Attributes:
        webhook_id: Unique identifier for the webhook registration.
        url: URL to receive webhook POST requests.
        events: List of event types to subscribe to.
        secret: Optional secret for webhook signature verification.
        is_active: Whether the webhook is currently active.
    
    Supports Requirement 28.1: Support webhook registration for events:
    indexing_complete, query_failed, low_confidence_answer, batch_complete.
    """
    webhook_id: str = Field(
        ...,
        description="Unique identifier for the webhook registration"
    )
    url: str = Field(
        ...,
        description="URL to receive webhook POST requests"
    )
    events: list[str] = Field(
        ...,
        min_length=1,
        description="List of event types to subscribe to"
    )
    secret: Optional[str] = Field(
        default=None,
        description="Optional secret for webhook signature verification"
    )
    is_active: bool = Field(
        default=True,
        description="Whether the webhook is currently active"
    )
    
    @field_validator('webhook_id')
    @classmethod
    def validate_webhook_id(cls, v: str) -> str:
        """Validate webhook_id is not empty."""
        if not v or not v.strip():
            raise ValueError("webhook_id cannot be empty")
        return v
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v or not v.strip():
            raise ValueError("url cannot be empty")
        if not v.startswith(('http://', 'https://')):
            raise ValueError("url must start with http:// or https://")
        return v
    
    @field_validator('events')
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        """Validate all events are valid event types."""
        for event in v:
            if event not in VALID_WEBHOOK_EVENTS:
                raise ValueError(
                    f"Invalid event type '{event}'. "
                    f"Valid events are: {sorted(VALID_WEBHOOK_EVENTS)}"
                )
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "webhook_id": "wh_abc123",
                "url": "https://example.com/webhooks/excel-rag",
                "events": ["indexing_complete", "query_failed"],
                "secret": "whsec_abc123xyz",
                "is_active": True
            }
        }


class WebhookDelivery(BaseModel):
    """
    Record of a webhook delivery attempt.
    
    Tracks the status and history of webhook delivery attempts,
    including retry information and response codes.
    
    Attributes:
        delivery_id: Unique identifier for the delivery attempt.
        webhook_id: ID of the webhook registration this delivery is for.
        event_type: Type of event that triggered the delivery.
        payload: Event payload sent in the webhook request.
        status: Delivery status (pending, delivered, failed).
        attempts: Number of delivery attempts made.
        last_attempt_at: Timestamp of the last delivery attempt.
        response_code: HTTP response code from the last attempt.
    
    Supports Requirement 28.1: Webhook delivery tracking.
    """
    delivery_id: str = Field(
        ...,
        description="Unique identifier for the delivery attempt"
    )
    webhook_id: str = Field(
        ...,
        description="ID of the webhook registration"
    )
    event_type: str = Field(
        ...,
        description="Type of event that triggered the delivery"
    )
    payload: dict[str, Any] = Field(
        ...,
        description="Event payload sent in the webhook request"
    )
    status: str = Field(
        ...,
        description="Delivery status: pending, delivered, failed"
    )
    attempts: int = Field(
        ...,
        ge=0,
        description="Number of delivery attempts made"
    )
    last_attempt_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the last delivery attempt"
    )
    response_code: Optional[int] = Field(
        default=None,
        ge=100,
        le=599,
        description="HTTP response code from the last attempt"
    )
    
    @field_validator('delivery_id', 'webhook_id')
    @classmethod
    def validate_ids_not_empty(cls, v: str) -> str:
        """Validate ID fields are not empty."""
        if not v or not v.strip():
            raise ValueError("ID field cannot be empty")
        return v
    
    @field_validator('event_type')
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        """Validate event_type is a valid event."""
        if v not in VALID_WEBHOOK_EVENTS:
            raise ValueError(
                f"Invalid event_type '{v}'. "
                f"Valid events are: {sorted(VALID_WEBHOOK_EVENTS)}"
            )
        return v
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is a valid value."""
        valid_statuses = {'pending', 'delivered', 'failed'}
        if v not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}, got '{v}'")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "delivery_id": "del_abc123",
                "webhook_id": "wh_abc123",
                "event_type": "indexing_complete",
                "payload": {
                    "file_id": "file_123",
                    "file_name": "sales_2024.xlsx",
                    "chunks_created": 42
                },
                "status": "delivered",
                "attempts": 1,
                "last_attempt_at": "2024-01-15T10:35:00Z",
                "response_code": 200
            }
        }


@dataclass
class AccessControlEntry:
    """
    Access control entry for file-level permissions.
    
    Defines the access permissions for a specific user on a specific file,
    enabling fine-grained access control for sensitive data.
    
    Attributes:
        file_id: ID of the file this entry applies to.
        user_id: ID of the user granted access.
        role: Role assigned to the user for this file.
        granted_at: Timestamp when access was granted.
        granted_by: User ID of the admin who granted access.
    
    Supports Requirement 29.1: Enforce role-based access control.
    """
    file_id: str
    user_id: str
    role: UserRole
    granted_at: datetime
    granted_by: str
    
    def __post_init__(self) -> None:
        """Validate required fields."""
        if not self.file_id or not self.file_id.strip():
            raise ValueError("file_id cannot be empty")
        if not self.user_id or not self.user_id.strip():
            raise ValueError("user_id cannot be empty")
        if not self.granted_by or not self.granted_by.strip():
            raise ValueError("granted_by cannot be empty")
        if not isinstance(self.role, UserRole):
            raise ValueError(f"role must be a UserRole enum, got {type(self.role)}")
        if not isinstance(self.granted_at, datetime):
            raise ValueError(f"granted_at must be a datetime, got {type(self.granted_at)}")


@dataclass
class AccessAuditLog:
    """
    Audit log entry for access attempts.
    
    Records all access attempts to protected resources for compliance
    and security auditing purposes.
    
    Attributes:
        log_id: Unique identifier for the log entry.
        user_id: ID of the user who attempted access.
        resource_type: Type of resource accessed (chunk, file, trace).
        resource_id: ID of the specific resource accessed.
        action: Action attempted (view, search, export).
        access_granted: Whether access was granted or denied.
        timestamp: When the access attempt occurred.
        ip_address: Optional IP address of the requester.
    
    Supports Requirement 29.1: Log all access attempts for audit purposes.
    """
    log_id: str
    user_id: str
    resource_type: str
    resource_id: str
    action: str
    access_granted: bool
    timestamp: datetime
    ip_address: Optional[str] = None
    
    # Valid resource types
    VALID_RESOURCE_TYPES = frozenset({'chunk', 'file', 'trace'})
    
    # Valid actions
    VALID_ACTIONS = frozenset({'view', 'search', 'export'})
    
    def __post_init__(self) -> None:
        """Validate required fields and enum values."""
        # Validate required string fields
        required_fields = [
            ('log_id', self.log_id),
            ('user_id', self.user_id),
            ('resource_type', self.resource_type),
            ('resource_id', self.resource_id),
            ('action', self.action),
        ]
        for field_name, value in required_fields:
            if not value or not value.strip():
                raise ValueError(f"{field_name} cannot be empty")
        
        # Validate resource_type
        if self.resource_type not in self.VALID_RESOURCE_TYPES:
            raise ValueError(
                f"resource_type must be one of {sorted(self.VALID_RESOURCE_TYPES)}, "
                f"got '{self.resource_type}'"
            )
        
        # Validate action
        if self.action not in self.VALID_ACTIONS:
            raise ValueError(
                f"action must be one of {sorted(self.VALID_ACTIONS)}, "
                f"got '{self.action}'"
            )
        
        # Validate timestamp
        if not isinstance(self.timestamp, datetime):
            raise ValueError(f"timestamp must be a datetime, got {type(self.timestamp)}")
        
        # Validate access_granted is boolean
        if not isinstance(self.access_granted, bool):
            raise ValueError(
                f"access_granted must be a boolean, got {type(self.access_granted)}"
            )
