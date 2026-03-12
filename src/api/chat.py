"""Chat session endpoints for web application"""

import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from src.api.web_auth import get_current_user
from src.api.dependencies import get_query_engine, get_conversation_manager
from src.query.query_engine import QueryEngine
from src.query.conversation_manager import ConversationManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class ChatQueryRequest(BaseModel):
    """Request for chat query"""
    query: str = Field(..., min_length=1, description="Natural language query")
    session_id: Optional[str] = Field(None, description="Session ID for conversation context")


class SourceCitation(BaseModel):
    """Source citation model"""
    file_name: str
    file_path: str
    sheet_name: str
    cell_range: Optional[str] = None
    citation_text: str


class ChatQueryResponse(BaseModel):
    """Response for chat query"""
    answer: Optional[str] = None
    sources: List[SourceCitation] = Field(default_factory=list)
    confidence: float
    session_id: str
    requires_clarification: bool = False
    clarification_question: Optional[str] = None
    clarification_options: List[dict] = Field(default_factory=list)
    processing_time_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionInfo(BaseModel):
    """Session information model"""
    session_id: str
    created_at: datetime
    last_activity: datetime
    query_count: int


class SessionListResponse(BaseModel):
    """Response for session list"""
    sessions: List[SessionInfo]
    total: int


class SessionCreateResponse(BaseModel):
    """Response for session creation"""
    session_id: str
    created_at: datetime
    message: str


class SessionDeleteResponse(BaseModel):
    """Response for session deletion"""
    success: bool
    message: str
    session_id: str


class MessageItem(BaseModel):
    """Single message in conversation history"""
    message_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    sources: List[SourceCitation] = Field(default_factory=list)
    confidence: Optional[float] = None


class SessionHistoryResponse(BaseModel):
    """Response for session history"""
    session_id: str
    messages: List[MessageItem]
    created_at: datetime
    last_activity: datetime


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/query", response_model=ChatQueryResponse)
async def submit_query(
    request: ChatQueryRequest,
    current_user: str = Depends(get_current_user),
    query_engine: QueryEngine = Depends(get_query_engine),
    conversation_manager: ConversationManager = Depends(get_conversation_manager)
):
    """
    Submit natural language query and get answer
    
    - **query**: Natural language question
    - **session_id**: Optional session ID for conversation context
    """
    logger.info(f"Chat query from user {current_user}: {request.query[:100]}")
    
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Process query
        start_time = datetime.utcnow()
        result = query_engine.process_query(
            query=request.query,
            session_id=session_id
        )
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Convert sources to response model
        sources = []
        for source in result.get("sources", []):
            sources.append(SourceCitation(
                file_name=source.get("file_name", ""),
                file_path=source.get("file_path", ""),
                sheet_name=source.get("sheet_name", ""),
                cell_range=source.get("cell_range"),
                citation_text=source.get("citation_text", "")
            ))
        
        # Store in conversation history
        conversation_manager.add_message(
            session_id=session_id,
            role="user",
            content=request.query
        )
        
        if result.get("answer"):
            conversation_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=result["answer"],
                metadata={
                    "sources": [s.dict() for s in sources],
                    "confidence": result.get("confidence", 0)
                }
            )
        
        logger.info(f"Query processed in {processing_time:.2f}ms, confidence: {result.get('confidence', 0)}")
        
        return ChatQueryResponse(
            answer=result.get("answer"),
            sources=sources,
            confidence=result.get("confidence", 0),
            session_id=session_id,
            requires_clarification=result.get("requires_clarification", False),
            clarification_question=result.get("clarification_question"),
            clarification_options=result.get("clarification_options", []),
            processing_time_ms=processing_time
        )
    
    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user: str = Depends(get_current_user),
    conversation_manager: ConversationManager = Depends(get_conversation_manager)
):
    """
    List all chat sessions for current user
    
    Returns list of sessions with metadata.
    """
    logger.info(f"Session list request from user {current_user}")
    
    try:
        # Get all sessions
        sessions = conversation_manager.get_all_sessions()
        
        # Convert to response model
        session_infos = []
        for session in sessions:
            session_infos.append(SessionInfo(
                session_id=session["session_id"],
                created_at=session["created_at"],
                last_activity=session["last_activity"],
                query_count=session["query_count"]
            ))
        
        return SessionListResponse(
            sessions=session_infos,
            total=len(session_infos)
        )
    
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}"
        )


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(
    current_user: str = Depends(get_current_user),
    conversation_manager: ConversationManager = Depends(get_conversation_manager)
):
    """
    Create new chat session
    
    Returns new session ID.
    """
    logger.info(f"Create session request from user {current_user}")
    
    try:
        # Generate new session ID
        session_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        
        # Initialize session in conversation manager
        conversation_manager.create_session(session_id)
        
        logger.info(f"Created new session: {session_id}")
        
        return SessionCreateResponse(
            session_id=session_id,
            created_at=created_at,
            message="Session created successfully"
        )
    
    except Exception as e:
        logger.error(f"Failed to create session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


@router.delete("/sessions/{session_id}", response_model=SessionDeleteResponse)
async def delete_session(
    session_id: str,
    current_user: str = Depends(get_current_user),
    conversation_manager: ConversationManager = Depends(get_conversation_manager)
):
    """
    Delete chat session and its history
    
    - **session_id**: Session ID to delete
    """
    logger.info(f"Delete session request from user {current_user}: {session_id}")
    
    try:
        # Delete session
        success = conversation_manager.delete_session(session_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_id}"
            )
        
        logger.info(f"Deleted session: {session_id}")
        
        return SessionDeleteResponse(
            success=True,
            message="Session deleted successfully",
            session_id=session_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )


@router.get("/sessions/{session_id}/history", response_model=SessionHistoryResponse)
async def get_session_history(
    session_id: str,
    current_user: str = Depends(get_current_user),
    conversation_manager: ConversationManager = Depends(get_conversation_manager)
):
    """
    Get conversation history for a session
    
    - **session_id**: Session ID
    """
    logger.info(f"Session history request from user {current_user}: {session_id}")
    
    try:
        # Get session history
        history = conversation_manager.get_session_history(session_id)
        
        if not history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_id}"
            )
        
        # Convert messages to response model
        messages = []
        for msg in history.get("messages", []):
            sources = []
            if msg.get("metadata", {}).get("sources"):
                for source in msg["metadata"]["sources"]:
                    sources.append(SourceCitation(**source))
            
            messages.append(MessageItem(
                message_id=msg.get("message_id", str(uuid.uuid4())),
                role=msg["role"],
                content=msg["content"],
                timestamp=msg["timestamp"],
                sources=sources,
                confidence=msg.get("metadata", {}).get("confidence")
            ))
        
        return SessionHistoryResponse(
            session_id=session_id,
            messages=messages,
            created_at=history["created_at"],
            last_activity=history["last_activity"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session history: {str(e)}"
        )
