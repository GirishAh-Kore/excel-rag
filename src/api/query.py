"""Query API endpoints"""

import logging
import time
import uuid
from typing import Dict, Any, List, AsyncGenerator
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query as QueryParam
from fastapi.responses import StreamingResponse
from src.api.models import (
    QueryRequest,
    QueryResponse,
    ClarificationRequest,
    QueryHistoryResponse,
    QueryHistoryItem,
    SessionContextResponse,
    QueryFeedbackRequest,
    QueryFeedbackResponse,
    ClearHistoryResponse,
    SourceCitation,
    ClarificationOption,
    ErrorResponse
)
from src.api.dependencies import (
    get_query_engine,
    get_generation_llm_service,
    get_conversation_manager,
    get_correlation_id
)
from src.api.web_auth import get_current_user
from src.query.query_engine import QueryEngine
from src.query.conversation_manager import ConversationManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=QueryResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Submit natural language query",
    description="Processes a natural language query and returns answer with sources"
)
async def query(
    request: QueryRequest,
    query_engine: QueryEngine = Depends(get_query_engine),
    conversation_manager: ConversationManager = Depends(get_conversation_manager),
    current_user: str = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Submit natural language query.
    
    Processes the query, retrieves relevant data from indexed Excel files,
    and generates an answer with source citations.
    """
    try:
        start_time = time.time()
        
        # Generate or use session ID
        session_id = request.session_id or str(uuid.uuid4())
        
        logger.info(
            f"Processing query",
            extra={
                'correlation_id': correlation_id,
                'session_id': session_id,
                'query': request.query[:100]  # Log first 100 chars
            }
        )
        
        # Ensure session exists
        if not conversation_manager.session_exists(session_id):
            conversation_manager.create_session(session_id)
        
        # Add user message to conversation history
        conversation_manager.add_message(
            session_id=session_id,
            role="user",
            content=request.query
        )
        
        # Process query (synchronous method)
        result = query_engine.process_query(
            query=request.query,
            session_id=session_id
        )
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Build response - result is a QueryResult Pydantic model
        sources = []
        for s in result.sources:
            file_name = getattr(s, 'file_name', '')
            sheet_name = getattr(s, 'sheet_name', '')
            cell_range = getattr(s, 'cell_range', None)
            
            # Generate citation text from available fields
            citation_parts = [file_name]
            if sheet_name:
                citation_parts.append(f"Sheet: {sheet_name}")
            if cell_range:
                citation_parts.append(f"Range: {cell_range}")
            citation_text = " | ".join(citation_parts)
            
            sources.append(SourceCitation(
                file_name=file_name,
                file_path=getattr(s, 'file_path', ''),
                sheet_name=sheet_name,
                cell_range=cell_range,
                citation_text=citation_text
            ))
        
        # Add assistant response to conversation history
        conversation_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=result.answer,
            metadata={
                "confidence": result.confidence,
                "sources": [s.file_name for s in sources],
                "requires_clarification": result.clarification_needed
            }
        )
        
        response = QueryResponse(
            answer=result.answer,
            sources=sources,
            confidence=result.confidence,
            session_id=session_id,
            requires_clarification=result.clarification_needed,
            clarification_question=result.clarifying_questions[0] if result.clarifying_questions else None,
            clarification_options=[],
            query_language='en',
            processing_time_ms=processing_time_ms
        )
        
        logger.info(
            f"Query processed successfully",
            extra={
                'correlation_id': correlation_id,
                'session_id': session_id,
                'confidence': response.confidence,
                'processing_time_ms': processing_time_ms,
                'requires_clarification': response.requires_clarification
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(
            f"Error processing query: {e}",
            extra={'correlation_id': correlation_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )


@router.post(
    "/clarify",
    response_model=QueryResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Session not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        501: {"model": ErrorResponse, "description": "Not implemented"}
    },
    summary="Respond to clarification question",
    description="Provides user's selection for a clarification question"
)
async def clarify(
    request: ClarificationRequest,
    query_engine: QueryEngine = Depends(get_query_engine),
    conversation_manager: ConversationManager = Depends(get_conversation_manager),
    current_user: str = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Respond to clarification question.
    
    Processes the user's selection from clarification options and continues query processing.
    """
    try:
        start_time = time.time()
        
        logger.info(
            f"Processing clarification response",
            extra={
                'correlation_id': correlation_id,
                'session_id': request.session_id,
                'selected_option': request.selected_option_id
            }
        )
        
        # Check if session exists using ConversationManager
        if not conversation_manager.session_exists(request.session_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {request.session_id} not found"
            )
        
        # Add clarification response as user message
        conversation_manager.add_message(
            session_id=request.session_id,
            role="user",
            content=f"Selected option: {request.selected_option_id}",
            metadata={"type": "clarification_response"}
        )
        
        # TODO: Implement full clarification flow
        # The QueryEngine.handle_clarification_response method requires:
        # - ClarificationRequest object (from clarification_generator)
        # - user_response string
        # This needs to be stored in session context when clarification is requested
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Return placeholder response indicating selection was received
        answer = (
            f"You selected option: {request.selected_option_id}. "
            f"Full clarification processing will be available in a future update."
        )
        
        # Add assistant response
        conversation_manager.add_message(
            session_id=request.session_id,
            role="assistant",
            content=answer,
            metadata={"type": "clarification_acknowledgment"}
        )
        
        response = QueryResponse(
            answer=answer,
            sources=[],
            confidence=0.5,
            session_id=request.session_id,
            requires_clarification=False,
            query_language='en',
            processing_time_ms=processing_time_ms
        )
        
        logger.info(
            f"Clarification response recorded",
            extra={
                'correlation_id': correlation_id,
                'session_id': request.session_id
            }
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error processing clarification: {e}",
            extra={'correlation_id': correlation_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process clarification: {str(e)}"
        )


@router.get(
    "/history",
    response_model=QueryHistoryResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get query history",
    description="Retrieves query history with pagination"
)
async def get_history(
    limit: int = QueryParam(10, ge=1, le=100, description="Maximum number of queries to return"),
    offset: int = QueryParam(0, ge=0, description="Number of queries to skip"),
    session_id: str = QueryParam(None, description="Filter by session ID"),
    conversation_manager: ConversationManager = Depends(get_conversation_manager),
    current_user: str = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Get query history.
    
    Returns paginated list of previous queries and their results.
    """
    try:
        logger.debug(
            f"Retrieving query history",
            extra={
                'correlation_id': correlation_id,
                'limit': limit,
                'offset': offset,
                'session_id': session_id
            }
        )
        
        all_queries: List[QueryHistoryItem] = []
        
        if session_id:
            # Get history for specific session
            messages = conversation_manager.get_messages(session_id)
            for i, msg in enumerate(messages):
                if msg.get('role') == 'user':
                    # Find corresponding assistant response
                    answer = None
                    confidence = 0.0
                    if i + 1 < len(messages) and messages[i + 1].get('role') == 'assistant':
                        answer = messages[i + 1].get('content')
                        confidence = messages[i + 1].get('metadata', {}).get('confidence', 0.0)
                    
                    all_queries.append(QueryHistoryItem(
                        query_id=msg.get('message_id', ''),
                        query=msg.get('content', ''),
                        answer=answer,
                        confidence=confidence,
                        timestamp=datetime.fromisoformat(msg['timestamp']) if isinstance(msg.get('timestamp'), str) else msg.get('timestamp', datetime.utcnow()),
                        session_id=session_id
                    ))
        else:
            # Get all sessions and their queries
            sessions = conversation_manager.get_all_sessions()
            for sess in sessions:
                sess_id = sess.get('session_id')
                messages = conversation_manager.get_messages(sess_id)
                for i, msg in enumerate(messages):
                    if msg.get('role') == 'user':
                        answer = None
                        confidence = 0.0
                        if i + 1 < len(messages) and messages[i + 1].get('role') == 'assistant':
                            answer = messages[i + 1].get('content')
                            confidence = messages[i + 1].get('metadata', {}).get('confidence', 0.0)
                        
                        all_queries.append(QueryHistoryItem(
                            query_id=msg.get('message_id', ''),
                            query=msg.get('content', ''),
                            answer=answer,
                            confidence=confidence,
                            timestamp=datetime.fromisoformat(msg['timestamp']) if isinstance(msg.get('timestamp'), str) else msg.get('timestamp', datetime.utcnow()),
                            session_id=sess_id
                        ))
        
        # Sort by timestamp (newest first)
        all_queries.sort(key=lambda q: q.timestamp, reverse=True)
        
        # Apply pagination
        total = len(all_queries)
        paginated_queries = all_queries[offset:offset + limit]
        
        return QueryHistoryResponse(
            queries=paginated_queries,
            total=total,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(
            f"Error retrieving query history: {e}",
            extra={'correlation_id': correlation_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve query history: {str(e)}"
        )


@router.delete(
    "/history",
    response_model=ClearHistoryResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Clear query history",
    description="Clears query history for current or all sessions"
)
async def clear_history(
    session_id: str = QueryParam(None, description="Clear specific session (or all if not provided)"),
    conversation_manager: ConversationManager = Depends(get_conversation_manager),
    current_user: str = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Clear query history.
    
    Clears query history for a specific session or all sessions.
    """
    try:
        logger.info(
            f"Clearing query history",
            extra={'correlation_id': correlation_id, 'session_id': session_id}
        )
        
        queries_deleted = 0
        
        if session_id:
            # Clear specific session
            session_history = conversation_manager.get_session_history(session_id)
            if session_history:
                queries_deleted = session_history.get('query_count', 0)
                conversation_manager.delete_session(session_id)
        else:
            # Clear all sessions
            sessions = conversation_manager.get_all_sessions()
            for sess in sessions:
                queries_deleted += sess.get('query_count', 0)
                conversation_manager.delete_session(sess['session_id'])
        
        logger.info(
            f"Query history cleared",
            extra={
                'correlation_id': correlation_id,
                'queries_deleted': queries_deleted
            }
        )
        
        return ClearHistoryResponse(
            success=True,
            queries_deleted=queries_deleted,
            message=f"Cleared {queries_deleted} queries"
        )
        
    except Exception as e:
        logger.error(
            f"Error clearing query history: {e}",
            extra={'correlation_id': correlation_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear query history: {str(e)}"
        )


@router.get(
    "/session/{session_id}",
    response_model=SessionContextResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        404: {"model": ErrorResponse, "description": "Session not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get session context",
    description="Retrieves context and history for a specific session"
)
async def get_session(
    session_id: str,
    conversation_manager: ConversationManager = Depends(get_conversation_manager),
    current_user: str = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Get session context.
    
    Returns session context including queries and selected files.
    """
    try:
        logger.debug(
            f"Retrieving session context",
            extra={'correlation_id': correlation_id, 'session_id': session_id}
        )
        
        # Get session history from ConversationManager
        session_history = conversation_manager.get_session_history(session_id)
        
        if not session_history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        # Build query history items from messages
        queries: List[QueryHistoryItem] = []
        messages = session_history.get('messages', [])
        
        for i, msg in enumerate(messages):
            if msg.get('role') == 'user':
                answer = None
                confidence = 0.0
                if i + 1 < len(messages) and messages[i + 1].get('role') == 'assistant':
                    answer = messages[i + 1].get('content')
                    confidence = messages[i + 1].get('metadata', {}).get('confidence', 0.0)
                
                queries.append(QueryHistoryItem(
                    query_id=msg.get('message_id', ''),
                    query=msg.get('content', ''),
                    answer=answer,
                    confidence=confidence,
                    timestamp=datetime.fromisoformat(msg['timestamp']) if isinstance(msg.get('timestamp'), str) else msg.get('timestamp', datetime.utcnow()),
                    session_id=session_id
                ))
        
        return SessionContextResponse(
            session_id=session_id,
            queries=queries,
            selected_files=session_history.get('selected_files', []),
            created_at=session_history.get('created_at', datetime.utcnow()),
            last_activity=session_history.get('last_activity', datetime.utcnow())
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error retrieving session context: {e}",
            extra={'correlation_id': correlation_id, 'session_id': session_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve session context: {str(e)}"
        )


@router.post(
    "/feedback",
    response_model=QueryFeedbackResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        404: {"model": ErrorResponse, "description": "Query not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Submit query feedback",
    description="Submits feedback on query results for preference learning"
)
async def submit_feedback(
    request: QueryFeedbackRequest,
    conversation_manager: ConversationManager = Depends(get_conversation_manager),
    current_user: str = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Submit query feedback.
    
    Records user feedback on query results to improve future file selection.
    
    Note: Feedback is logged for analytics. Full preference learning
    integration will be available in a future update.
    """
    try:
        logger.info(
            f"Recording query feedback",
            extra={
                'correlation_id': correlation_id,
                'query_id': request.query_id,
                'helpful': request.helpful
            }
        )
        
        # Log feedback for analytics (preference learning integration TODO)
        # In a full implementation, this would:
        # 1. Find the query by ID across sessions
        # 2. Store feedback in a dedicated feedback store
        # 3. Update preference models
        
        logger.info(
            f"Query feedback recorded",
            extra={
                'correlation_id': correlation_id,
                'query_id': request.query_id,
                'helpful': request.helpful,
                'selected_file': request.selected_file,
                'has_comments': bool(request.comments)
            }
        )
        
        return QueryFeedbackResponse(
            success=True,
            message="Feedback recorded successfully"
        )
        
    except Exception as e:
        logger.error(
            f"Error recording feedback: {e}",
            extra={'correlation_id': correlation_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record feedback: {str(e)}"
        )


@router.post(
    "/stream",
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Stream query response",
    description="Processes a query and streams the answer token-by-token via Server-Sent Events"
)
async def stream_query(
    request: QueryRequest,
    llm_service=Depends(get_generation_llm_service),
    current_user: str = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Stream a query response using Server-Sent Events.

    Returns text/event-stream with data chunks as they are generated.
    """
    async def _generate() -> AsyncGenerator[str, None]:
        try:
            system_prompt = (
                "You are a helpful assistant that answers questions about Excel data. "
                "Be concise and cite specific values when available."
            )
            for chunk in llm_service.stream_generate(
                prompt=request.query,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=1000
            ):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}", extra={"correlation_id": correlation_id})
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
