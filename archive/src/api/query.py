"""Query API endpoints"""

import logging
import time
import uuid
from typing import Dict, Any, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query as QueryParam
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
    require_authentication,
    get_correlation_id
)
from src.query.query_engine import QueryEngine

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage (in production, use Redis or database)
query_history: Dict[str, List[Dict[str, Any]]] = {}  # {session_id: [queries]}
session_contexts: Dict[str, Dict[str, Any]] = {}  # {session_id: context}


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
    auth_service = Depends(require_authentication),
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
        
        # Process query
        result = await query_engine.process_query(
            query=request.query,
            session_id=session_id,
            language=request.language
        )
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Generate query ID
        query_id = str(uuid.uuid4())
        
        # Store in history
        if session_id not in query_history:
            query_history[session_id] = []
        
        query_history[session_id].append({
            'query_id': query_id,
            'query': request.query,
            'answer': result.get('answer'),
            'confidence': result.get('confidence', 0),
            'timestamp': datetime.utcnow(),
            'session_id': session_id
        })
        
        # Update session context
        if session_id not in session_contexts:
            session_contexts[session_id] = {
                'session_id': session_id,
                'created_at': datetime.utcnow(),
                'last_activity': datetime.utcnow(),
                'selected_files': []
            }
        else:
            session_contexts[session_id]['last_activity'] = datetime.utcnow()
        
        # Add selected files to context
        if result.get('sources'):
            for source in result['sources']:
                file_name = source.get('file_name')
                if file_name and file_name not in session_contexts[session_id]['selected_files']:
                    session_contexts[session_id]['selected_files'].append(file_name)
        
        # Build response
        response = QueryResponse(
            answer=result.get('answer'),
            sources=[
                SourceCitation(
                    file_name=s.get('file_name', ''),
                    file_path=s.get('file_path', ''),
                    sheet_name=s.get('sheet_name', ''),
                    cell_range=s.get('cell_range'),
                    citation_text=s.get('citation_text', '')
                )
                for s in result.get('sources', [])
            ],
            confidence=result.get('confidence', 0),
            session_id=session_id,
            requires_clarification=result.get('requires_clarification', False),
            clarification_question=result.get('clarification_question'),
            clarification_options=[
                ClarificationOption(
                    option_id=opt.get('option_id', ''),
                    description=opt.get('description', ''),
                    file_name=opt.get('file_name'),
                    confidence=opt.get('confidence', 0)
                )
                for opt in result.get('clarification_options', [])
            ],
            query_language=result.get('query_language', 'en'),
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
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Respond to clarification question",
    description="Provides user's selection for a clarification question"
)
async def clarify(
    request: ClarificationRequest,
    query_engine: QueryEngine = Depends(get_query_engine),
    auth_service = Depends(require_authentication),
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
        
        # Check if session exists
        if request.session_id not in session_contexts:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {request.session_id} not found"
            )
        
        # Process clarification
        result = await query_engine.process_clarification(
            session_id=request.session_id,
            selected_option_id=request.selected_option_id
        )
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Build response
        response = QueryResponse(
            answer=result.get('answer'),
            sources=[
                SourceCitation(
                    file_name=s.get('file_name', ''),
                    file_path=s.get('file_path', ''),
                    sheet_name=s.get('sheet_name', ''),
                    cell_range=s.get('cell_range'),
                    citation_text=s.get('citation_text', '')
                )
                for s in result.get('sources', [])
            ],
            confidence=result.get('confidence', 0),
            session_id=request.session_id,
            requires_clarification=False,
            query_language=result.get('query_language', 'en'),
            processing_time_ms=processing_time_ms
        )
        
        logger.info(
            f"Clarification processed successfully",
            extra={
                'correlation_id': correlation_id,
                'session_id': request.session_id,
                'confidence': response.confidence
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
    auth_service = Depends(require_authentication),
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
        
        # Collect all queries
        all_queries = []
        
        if session_id:
            # Filter by session
            if session_id in query_history:
                all_queries = query_history[session_id]
        else:
            # Get all queries from all sessions
            for queries in query_history.values():
                all_queries.extend(queries)
        
        # Sort by timestamp (newest first)
        all_queries.sort(key=lambda q: q['timestamp'], reverse=True)
        
        # Apply pagination
        total = len(all_queries)
        paginated_queries = all_queries[offset:offset + limit]
        
        # Build response
        return QueryHistoryResponse(
            queries=[
                QueryHistoryItem(
                    query_id=q['query_id'],
                    query=q['query'],
                    answer=q.get('answer'),
                    confidence=q['confidence'],
                    timestamp=q['timestamp'],
                    session_id=q['session_id']
                )
                for q in paginated_queries
            ],
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
    auth_service = Depends(require_authentication),
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
            if session_id in query_history:
                queries_deleted = len(query_history[session_id])
                del query_history[session_id]
            if session_id in session_contexts:
                del session_contexts[session_id]
        else:
            # Clear all sessions
            for queries in query_history.values():
                queries_deleted += len(queries)
            query_history.clear()
            session_contexts.clear()
        
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
    auth_service = Depends(require_authentication),
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
        
        # Check if session exists
        if session_id not in session_contexts:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        context = session_contexts[session_id]
        queries = query_history.get(session_id, [])
        
        return SessionContextResponse(
            session_id=session_id,
            queries=[
                QueryHistoryItem(
                    query_id=q['query_id'],
                    query=q['query'],
                    answer=q.get('answer'),
                    confidence=q['confidence'],
                    timestamp=q['timestamp'],
                    session_id=q['session_id']
                )
                for q in queries
            ],
            selected_files=context.get('selected_files', []),
            created_at=context['created_at'],
            last_activity=context['last_activity']
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
    auth_service = Depends(require_authentication),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Submit query feedback.
    
    Records user feedback on query results to improve future file selection.
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
        
        # Find query in history
        query_found = False
        for queries in query_history.values():
            for q in queries:
                if q['query_id'] == request.query_id:
                    q['feedback'] = {
                        'helpful': request.helpful,
                        'selected_file': request.selected_file,
                        'comments': request.comments,
                        'timestamp': datetime.utcnow()
                    }
                    query_found = True
                    break
            if query_found:
                break
        
        if not query_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Query {request.query_id} not found"
            )
        
        # TODO: Store feedback in preference manager for learning
        
        logger.info(
            f"Query feedback recorded",
            extra={'correlation_id': correlation_id, 'query_id': request.query_id}
        )
        
        return QueryFeedbackResponse(
            success=True,
            message="Feedback recorded successfully"
        )
        
    except HTTPException:
        raise
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
