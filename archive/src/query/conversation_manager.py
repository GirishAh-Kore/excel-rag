"""
Conversation Context Manager

Manages conversation state across multiple queries in a session.
Stores previous queries, selected files, and context to resolve
ambiguous references in follow-up questions.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field

from src.abstractions.cache_service import CacheService
from src.models.domain_models import ConversationContext

logger = logging.getLogger(__name__)


class SessionData(BaseModel):
    """Data stored for a conversation session."""
    
    session_id: str = Field(..., description="Unique session identifier")
    previous_queries: List[str] = Field(
        default_factory=list,
        description="Previous queries in this session"
    )
    selected_files: List[str] = Field(
        default_factory=list,
        description="File IDs selected in this session"
    )
    selected_sheets: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Sheet names selected per file (file_id -> [sheet_names])"
    )
    last_query_results: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Results from last query for context"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When session was created"
    )
    last_accessed: datetime = Field(
        default_factory=datetime.now,
        description="When session was last accessed"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "previous_queries": ["What were the expenses in January?"],
                "selected_files": ["file123"],
                "selected_sheets": {"file123": ["Summary"]},
                "last_query_results": None,
                "created_at": "2024-01-15T10:00:00",
                "last_accessed": "2024-01-15T10:05:00"
            }
        }


class ConversationManager:
    """
    Manages conversation context across multiple queries.
    
    Features:
    - Session creation and management
    - Context storage using cache service
    - Session timeout (30 minutes)
    - Follow-up question resolution
    - Query history tracking
    """
    
    # Session timeout in seconds (30 minutes)
    SESSION_TIMEOUT = 30 * 60
    
    # Cache key prefix
    CACHE_PREFIX = "conversation:session:"
    
    def __init__(self, cache_service: CacheService):
        """
        Initialize ConversationManager.
        
        Args:
            cache_service: Cache service for storing session data
        """
        self.cache_service = cache_service
        logger.info("ConversationManager initialized")
    
    def create_session(self) -> str:
        """
        Create a new conversation session.
        
        Returns:
            Session ID
        """
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        
        session_data = SessionData(
            session_id=session_id,
            previous_queries=[],
            selected_files=[],
            selected_sheets={},
            last_query_results=None
        )
        
        self._save_session(session_data)
        
        logger.info(f"Created new session: {session_id}")
        return session_id
    
    def get_context(self, session_id: str) -> Optional[ConversationContext]:
        """
        Get conversation context for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ConversationContext or None if session not found
        """
        session_data = self._load_session(session_id)
        
        if not session_data:
            logger.warning(f"Session not found: {session_id}")
            return None
        
        # Update last accessed time
        session_data.last_accessed = datetime.now()
        self._save_session(session_data)
        
        return ConversationContext(
            previous_queries=session_data.previous_queries,
            selected_files=session_data.selected_files,
            session_id=session_id
        )
    
    def update_context(
        self,
        session_id: str,
        query: Optional[str] = None,
        selected_file: Optional[str] = None,
        selected_sheet: Optional[str] = None,
        query_results: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update conversation context with new information.
        
        Args:
            session_id: Session identifier
            query: New query to add to history
            selected_file: File ID that was selected
            selected_sheet: Sheet name that was selected
            query_results: Results from the query
            
        Returns:
            True if successful, False otherwise
        """
        session_data = self._load_session(session_id)
        
        if not session_data:
            logger.warning(f"Cannot update non-existent session: {session_id}")
            return False
        
        # Add query to history
        if query:
            session_data.previous_queries.append(query)
            # Keep only last 10 queries
            session_data.previous_queries = session_data.previous_queries[-10:]
        
        # Add selected file
        if selected_file and selected_file not in session_data.selected_files:
            session_data.selected_files.append(selected_file)
            # Keep only last 5 files
            session_data.selected_files = session_data.selected_files[-5:]
        
        # Add selected sheet
        if selected_file and selected_sheet:
            if selected_file not in session_data.selected_sheets:
                session_data.selected_sheets[selected_file] = []
            if selected_sheet not in session_data.selected_sheets[selected_file]:
                session_data.selected_sheets[selected_file].append(selected_sheet)
        
        # Store query results
        if query_results:
            session_data.last_query_results = query_results
        
        # Update last accessed time
        session_data.last_accessed = datetime.now()
        
        # Save updated session
        self._save_session(session_data)
        
        logger.debug(f"Updated context for session: {session_id}")
        return True
    
    def clear_context(self, session_id: str) -> bool:
        """
        Clear conversation context for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        cache_key = self._get_cache_key(session_id)
        success = self.cache_service.delete(cache_key)
        
        if success:
            logger.info(f"Cleared context for session: {session_id}")
        else:
            logger.warning(f"Failed to clear context for session: {session_id}")
        
        return success
    
    def get_last_query(self, session_id: str) -> Optional[str]:
        """
        Get the last query from a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Last query or None
        """
        session_data = self._load_session(session_id)
        
        if not session_data or not session_data.previous_queries:
            return None
        
        return session_data.previous_queries[-1]
    
    def get_last_selected_file(self, session_id: str) -> Optional[str]:
        """
        Get the last selected file from a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Last selected file ID or None
        """
        session_data = self._load_session(session_id)
        
        if not session_data or not session_data.selected_files:
            return None
        
        return session_data.selected_files[-1]
    
    def get_last_selected_sheet(
        self,
        session_id: str,
        file_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Get the last selected sheet from a session.
        
        Args:
            session_id: Session identifier
            file_id: Optional file ID to get sheet for (uses last file if not provided)
            
        Returns:
            Last selected sheet name or None
        """
        session_data = self._load_session(session_id)
        
        if not session_data:
            return None
        
        # Use provided file_id or last selected file
        target_file = file_id or self.get_last_selected_file(session_id)
        
        if not target_file or target_file not in session_data.selected_sheets:
            return None
        
        sheets = session_data.selected_sheets[target_file]
        return sheets[-1] if sheets else None
    
    def resolve_ambiguous_reference(
        self,
        query: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Resolve ambiguous references in follow-up questions.
        
        Args:
            query: Current query with potential ambiguous references
            session_id: Session identifier
            
        Returns:
            Dictionary with resolved references
        """
        session_data = self._load_session(session_id)
        
        if not session_data:
            return {}
        
        resolved = {}
        query_lower = query.lower()
        
        # Check for temporal references that might refer to previous context
        if any(word in query_lower for word in ["it", "that", "this", "same"]):
            # User might be referring to the last file/sheet
            last_file = self.get_last_selected_file(session_id)
            if last_file:
                resolved["implied_file"] = last_file
            
            last_sheet = self.get_last_selected_sheet(session_id)
            if last_sheet:
                resolved["implied_sheet"] = last_sheet
        
        # Check for follow-up indicators
        if any(word in query_lower for word in ["also", "too", "additionally", "what about"]):
            resolved["is_follow_up"] = True
            resolved["previous_query"] = self.get_last_query(session_id)
        
        # Check for comparison with previous results
        if any(word in query_lower for word in ["compare", "difference", "vs"]):
            if session_data.last_query_results:
                resolved["previous_results"] = session_data.last_query_results
        
        return resolved
    
    def _save_session(self, session_data: SessionData) -> bool:
        """
        Save session data to cache.
        
        Args:
            session_data: Session data to save
            
        Returns:
            True if successful
        """
        cache_key = self._get_cache_key(session_data.session_id)
        
        # Serialize to JSON
        session_json = session_data.model_dump_json()
        
        # Save with TTL
        success = self.cache_service.set(
            key=cache_key,
            value=session_json,
            ttl=self.SESSION_TIMEOUT
        )
        
        return success
    
    def _load_session(self, session_id: str) -> Optional[SessionData]:
        """
        Load session data from cache.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionData or None if not found
        """
        cache_key = self._get_cache_key(session_id)
        
        session_json = self.cache_service.get(cache_key)
        
        if not session_json:
            return None
        
        try:
            # Deserialize from JSON
            if isinstance(session_json, str):
                session_data = SessionData.model_validate_json(session_json)
            else:
                # If cache returns dict directly
                session_data = SessionData.model_validate(session_json)
            
            return session_data
            
        except Exception as e:
            logger.error(f"Error loading session data: {e}", exc_info=True)
            return None
    
    def _get_cache_key(self, session_id: str) -> str:
        """
        Get cache key for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Cache key
        """
        return f"{self.CACHE_PREFIX}{session_id}"
    
    def list_active_sessions(self) -> List[str]:
        """
        List all active session IDs.
        
        Note: This requires cache service to support pattern matching.
        May not be available in all cache implementations.
        
        Returns:
            List of active session IDs
        """
        # This would require the cache service to support listing keys by pattern
        # For now, return empty list as this is not critical functionality
        logger.warning("list_active_sessions not fully implemented")
        return []
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics about a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session statistics or None
        """
        session_data = self._load_session(session_id)
        
        if not session_data:
            return None
        
        return {
            "session_id": session_id,
            "query_count": len(session_data.previous_queries),
            "file_count": len(session_data.selected_files),
            "sheet_count": sum(len(sheets) for sheets in session_data.selected_sheets.values()),
            "created_at": session_data.created_at.isoformat(),
            "last_accessed": session_data.last_accessed.isoformat(),
            "age_seconds": (datetime.now() - session_data.created_at).total_seconds()
        }
