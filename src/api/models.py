"""Pydantic models for API request/response validation"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


# ============================================================================
# Common Models
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str = Field(..., description="Error type or code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID for tracing")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


# ============================================================================
# Authentication Models
# ============================================================================

class AuthLoginResponse(BaseModel):
    """Response for auth login endpoint"""
    authorization_url: str = Field(..., description="URL for user to authorize access")
    state: str = Field(..., description="State parameter for CSRF protection")


class AuthCallbackRequest(BaseModel):
    """Request for auth callback endpoint"""
    code: str = Field(..., description="Authorization code from OAuth callback")
    state: str = Field(..., description="State parameter for validation")


class AuthCallbackResponse(BaseModel):
    """Response for auth callback endpoint"""
    success: bool = Field(..., description="Whether authentication was successful")
    message: str = Field(..., description="Status message")


class AuthStatusResponse(BaseModel):
    """Response for auth status endpoint"""
    authenticated: bool = Field(..., description="Whether user is authenticated")
    token_expiry: Optional[datetime] = Field(None, description="Token expiration time")
    user_email: Optional[str] = Field(None, description="Authenticated user email")


class AuthLogoutResponse(BaseModel):
    """Response for auth logout endpoint"""
    success: bool = Field(..., description="Whether logout was successful")
    message: str = Field(..., description="Status message")


# ============================================================================
# Indexing Models
# ============================================================================

class IndexRequest(BaseModel):
    """Request for indexing operations"""
    folder_id: Optional[str] = Field(None, description="Specific folder ID to index (optional)")
    file_filters: Optional[List[str]] = Field(None, description="File name patterns to filter")
    force_reindex: bool = Field(False, description="Force reindexing even if files haven't changed")


class IndexResponse(BaseModel):
    """Response for indexing initiation"""
    job_id: str = Field(..., description="Unique job ID for tracking progress")
    status: str = Field(..., description="Initial job status")
    message: str = Field(..., description="Status message")


class IndexStatusResponse(BaseModel):
    """Response for indexing status check"""
    job_id: str = Field(..., description="Job ID")
    status: str = Field(..., description="Current status (running, paused, completed, failed)")
    progress_percentage: float = Field(..., description="Progress percentage (0-100)")
    current_file: Optional[str] = Field(None, description="Currently processing file")
    files_processed: int = Field(..., description="Number of files processed")
    files_total: int = Field(..., description="Total number of files to process")
    started_at: datetime = Field(..., description="Job start time")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")


class IndexReportResponse(BaseModel):
    """Response for indexing report"""
    job_id: str = Field(..., description="Job ID")
    status: str = Field(..., description="Final status")
    files_processed: int = Field(..., description="Number of files successfully processed")
    files_failed: int = Field(..., description="Number of files that failed")
    files_skipped: int = Field(..., description="Number of files skipped")
    sheets_indexed: int = Field(..., description="Total sheets indexed")
    embeddings_generated: int = Field(..., description="Total embeddings generated")
    duration_seconds: float = Field(..., description="Total duration in seconds")
    started_at: datetime = Field(..., description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    errors: Optional[List[str]] = Field(None, description="List of errors encountered")


class IndexControlResponse(BaseModel):
    """Response for index control operations (pause, resume, stop)"""
    job_id: str = Field(..., description="Job ID")
    action: str = Field(..., description="Action performed (pause, resume, stop)")
    success: bool = Field(..., description="Whether action was successful")
    message: str = Field(..., description="Status message")


# ============================================================================
# Query Models
# ============================================================================

class QueryRequest(BaseModel):
    """Request for query endpoint"""
    query: str = Field(..., description="Natural language query", min_length=1)
    session_id: Optional[str] = Field(None, description="Session ID for conversation context")
    language: Optional[str] = Field(None, description="Query language (auto-detected if not provided)")
    
    @validator('query')
    def query_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty')
        return v.strip()


class SourceCitation(BaseModel):
    """Source citation for query results"""
    file_name: str = Field(..., description="Source file name")
    file_path: str = Field(..., description="Full file path")
    sheet_name: str = Field(..., description="Sheet name")
    cell_range: Optional[str] = Field(None, description="Cell range (e.g., 'B10:D15')")
    citation_text: str = Field(..., description="Formatted citation text")


class ClarificationOption(BaseModel):
    """Clarification option for ambiguous queries"""
    option_id: str = Field(..., description="Unique option ID")
    description: str = Field(..., description="Option description")
    file_name: Optional[str] = Field(None, description="Associated file name")
    confidence: float = Field(..., description="Confidence score (0-1)")


class QueryResponse(BaseModel):
    """Response for query endpoint"""
    answer: Optional[str] = Field(None, description="Generated answer")
    sources: List[SourceCitation] = Field(default_factory=list, description="Source citations")
    confidence: float = Field(..., description="Confidence score (0-100)")
    session_id: str = Field(..., description="Session ID for follow-up queries")
    requires_clarification: bool = Field(False, description="Whether clarification is needed")
    clarification_question: Optional[str] = Field(None, description="Clarification question")
    clarification_options: List[ClarificationOption] = Field(default_factory=list, description="Clarification options")
    query_language: str = Field(..., description="Detected query language")
    processing_time_ms: float = Field(..., description="Query processing time in milliseconds")


class ClarificationRequest(BaseModel):
    """Request for clarification response"""
    session_id: str = Field(..., description="Session ID from original query")
    selected_option_id: str = Field(..., description="Selected clarification option ID")


class QueryHistoryItem(BaseModel):
    """Single query history item"""
    query_id: str = Field(..., description="Unique query ID")
    query: str = Field(..., description="Original query text")
    answer: Optional[str] = Field(None, description="Generated answer")
    confidence: float = Field(..., description="Confidence score")
    timestamp: datetime = Field(..., description="Query timestamp")
    session_id: str = Field(..., description="Session ID")


class QueryHistoryResponse(BaseModel):
    """Response for query history endpoint"""
    queries: List[QueryHistoryItem] = Field(..., description="List of query history items")
    total: int = Field(..., description="Total number of queries in history")
    limit: int = Field(..., description="Limit applied")
    offset: int = Field(..., description="Offset applied")


class SessionContextResponse(BaseModel):
    """Response for session context endpoint"""
    session_id: str = Field(..., description="Session ID")
    queries: List[QueryHistoryItem] = Field(..., description="Queries in this session")
    selected_files: List[str] = Field(default_factory=list, description="Files selected in this session")
    created_at: datetime = Field(..., description="Session creation time")
    last_activity: datetime = Field(..., description="Last activity time")


class QueryFeedbackRequest(BaseModel):
    """Request for query feedback"""
    query_id: str = Field(..., description="Query ID to provide feedback for")
    helpful: bool = Field(..., description="Whether the answer was helpful")
    selected_file: Optional[str] = Field(None, description="File that was actually relevant")
    comments: Optional[str] = Field(None, description="Additional feedback comments")


class QueryFeedbackResponse(BaseModel):
    """Response for query feedback"""
    success: bool = Field(..., description="Whether feedback was recorded")
    message: str = Field(..., description="Status message")


class ClearHistoryResponse(BaseModel):
    """Response for clearing query history"""
    success: bool = Field(..., description="Whether history was cleared")
    queries_deleted: int = Field(..., description="Number of queries deleted")
    message: str = Field(..., description="Status message")
