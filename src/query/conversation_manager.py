"""
Conversation Context Manager

Manages conversation state across multiple queries in a session.
Stores previous queries, selected files, and context to resolve
ambiguous references in follow-up questions.

This module provides:
- Session creation and lifecycle management
- Full message history tracking (user and assistant messages)
- Context storage using pluggable cache service
- Session timeout with automatic expiration
- Follow-up question resolution using conversation context
- Query history tracking for analytics
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field

from src.abstractions.cache_service import CacheService
from src.config import ConversationConfig
from src.models.domain_models import ConversationContext

logger = logging.getLogger(__name__)


class MessageData(BaseModel):
    """Represents a single message in a conversation."""
    
    message_id: str = Field(..., description="Unique message identifier")
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now, description="When message was created")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (sources, confidence, etc.)"
    )


class SessionData(BaseModel):
    """Data stored for a conversation session."""
    
    session_id: str = Field(..., description="Unique session identifier")
    messages: List[MessageData] = Field(
        default_factory=list,
        description="Full message history for this session"
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
    
    @property
    def previous_queries(self) -> List[str]:
        """Extract user queries from message history for backward compatibility."""
        return [msg.content for msg in self.messages if msg.role == "user"]
    
    @property
    def query_count(self) -> int:
        """Count of user queries in this session."""
        return len([msg for msg in self.messages if msg.role == "user"])
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "messages": [
                    {
                        "message_id": "msg_001",
                        "role": "user",
                        "content": "What were the expenses in January?",
                        "timestamp": "2024-01-15T10:00:00",
                        "metadata": {}
                    },
                    {
                        "message_id": "msg_002",
                        "role": "assistant",
                        "content": "The total expenses for January were $7,000.",
                        "timestamp": "2024-01-15T10:00:01",
                        "metadata": {"confidence": 0.95}
                    }
                ],
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
    
    This class provides comprehensive session management including:
    - Session creation, retrieval, and deletion
    - Full message history tracking with metadata
    - Context storage using pluggable cache service
    - Session timeout (configurable via ConversationConfig)
    - Follow-up question resolution using conversation context
    - Query history tracking for analytics and debugging
    
    The manager uses a cache service for storage, allowing for different
    backends (Redis for production, in-memory for development).
    """
    
    def __init__(
        self,
        cache_service: CacheService,
        config: Optional[ConversationConfig] = None
    ):
        """
        Initialize ConversationManager.
        
        Args:
            cache_service: Cache service for storing session data.
                          Supports Redis (production) or in-memory (development).
            config: Optional conversation configuration. If not provided,
                   uses default ConversationConfig values.
        """
        self.cache_service = cache_service
        self.config = config or ConversationConfig()
        
        # Use config values instead of hardcoded constants
        self.session_timeout = self.config.session_timeout_seconds
        self.max_messages_per_session = self.config.max_messages_per_session
        self.max_files_per_session = self.config.max_files_per_session
        self.cache_prefix = self.config.cache_prefix
        
        logger.info("ConversationManager initialized")
    
    # =========================================================================
    # Session Lifecycle Management
    # =========================================================================
    
    def create_session(self, session_id: Optional[str] = None) -> str:
        """
        Create a new conversation session.
        
        Args:
            session_id: Optional custom session ID. If not provided, generates one.
        
        Returns:
            Session ID (generated or provided)
        """
        if session_id is None:
            session_id = f"sess_{uuid.uuid4().hex[:12]}"
        
        session_data = SessionData(
            session_id=session_id,
            messages=[],
            selected_files=[],
            selected_sheets={},
            last_query_results=None,
            created_at=datetime.now(),
            last_accessed=datetime.now()
        )
        
        self._save_session(session_data)
        
        logger.info(f"Created new session: {session_id}")
        return session_id
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was deleted, False if not found
        """
        cache_key = self._get_cache_key(session_id)
        success = self.cache_service.delete(cache_key)
        
        if success:
            logger.info(f"Deleted session: {session_id}")
        else:
            logger.warning(f"Session not found for deletion: {session_id}")
        
        return success
    
    def session_exists(self, session_id: str) -> bool:
        """
        Check if a session exists.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session exists
        """
        return self._load_session(session_id) is not None
    
    # =========================================================================
    # Message Management
    # =========================================================================
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a message to session history.
        
        Args:
            session_id: Session identifier
            role: Message role ("user" or "assistant")
            content: Message content
            metadata: Optional metadata (sources, confidence, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        if role not in ("user", "assistant"):
            logger.error(f"Invalid message role: {role}")
            return False
        
        session_data = self._load_session(session_id)
        
        if not session_data:
            # Auto-create session if it doesn't exist
            logger.info(f"Auto-creating session for message: {session_id}")
            self.create_session(session_id)
            session_data = self._load_session(session_id)
            
            if not session_data:
                logger.error(f"Failed to create session: {session_id}")
                return False
        
        # Create message
        message = MessageData(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        # Add message to history
        session_data.messages.append(message)
        
        # Trim old messages if exceeding limit
        if len(session_data.messages) > self.max_messages_per_session:
            session_data.messages = session_data.messages[-self.max_messages_per_session:]
        
        # Update last_query_results for assistant messages with metadata
        if role == "assistant" and metadata:
            session_data.last_query_results = {
                "answer": content,
                **metadata
            }
        
        # Update last accessed time
        session_data.last_accessed = datetime.now()
        
        # Save session
        success = self._save_session(session_data)
        
        if success:
            logger.debug(f"Added {role} message to session {session_id}")
        
        return success
    
    def get_messages(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get messages from a session.
        
        Args:
            session_id: Session identifier
            limit: Optional limit on number of messages (most recent)
            
        Returns:
            List of message dictionaries
        """
        session_data = self._load_session(session_id)
        
        if not session_data:
            return []
        
        messages = session_data.messages
        
        if limit and limit > 0:
            messages = messages[-limit:]
        
        return [msg.model_dump() for msg in messages]
    
    # =========================================================================
    # Session History and Context
    # =========================================================================
    
    def get_session_history(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full session history including all messages.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session history or None if not found
        """
        session_data = self._load_session(session_id)
        
        if not session_data:
            return None
        
        return {
            "session_id": session_id,
            "messages": [msg.model_dump() for msg in session_data.messages],
            "created_at": session_data.created_at,
            "last_activity": session_data.last_accessed,
            "query_count": session_data.query_count,
            "selected_files": session_data.selected_files
        }
    
    def get_context(self, session_id: str) -> Optional[ConversationContext]:
        """
        Get conversation context for a session.
        
        This is used by the query engine to resolve ambiguous references
        and maintain conversation continuity.
        
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
        
        This method is called after query processing to update the session
        with new selections and results.
        
        Args:
            session_id: Session identifier
            query: New query to add to history (deprecated, use add_message)
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
        
        # Add query as user message (backward compatibility)
        if query:
            self.add_message(session_id, "user", query)
            # Reload session after adding message
            session_data = self._load_session(session_id)
        
        # Add selected file
        if selected_file and selected_file not in session_data.selected_files:
            session_data.selected_files.append(selected_file)
            # Keep only recent files
            if len(session_data.selected_files) > self.max_files_per_session:
                session_data.selected_files = session_data.selected_files[-self.max_files_per_session:]
        
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
        success = self._save_session(session_data)
        
        if success:
            logger.debug(f"Updated context for session: {session_id}")
        
        return success
    
    def clear_context(self, session_id: str) -> bool:
        """
        Clear conversation context for a session (alias for delete_session).
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        return self.delete_session(session_id)
    
    # =========================================================================
    # Session Listing and Statistics
    # =========================================================================
    
    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """
        Get summary information for all active sessions.
        
        Note: This method's effectiveness depends on the cache service's
        ability to list keys by pattern. In-memory cache supports this,
        but some Redis configurations may not.
        
        Returns:
            List of session summary dictionaries
        """
        # Try to get keys matching our prefix
        try:
            if hasattr(self.cache_service, 'keys'):
                pattern = f"{self.cache_prefix}*"
                keys = self.cache_service.keys(pattern)
                
                sessions = []
                for key in keys:
                    # Extract session_id from key
                    session_id = key.replace(self.cache_prefix, "")
                    session_data = self._load_session(session_id)
                    
                    if session_data:
                        sessions.append({
                            "session_id": session_id,
                            "created_at": session_data.created_at,
                            "last_activity": session_data.last_accessed,
                            "query_count": session_data.query_count
                        })
                
                return sessions
        except Exception as e:
            logger.warning(f"Could not list sessions: {e}")
        
        # Fallback: return empty list if key listing not supported
        logger.debug("Session listing not supported by cache backend")
        return []
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed statistics about a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session statistics or None if not found
        """
        session_data = self._load_session(session_id)
        
        if not session_data:
            return None
        
        return {
            "session_id": session_id,
            "query_count": session_data.query_count,
            "message_count": len(session_data.messages),
            "file_count": len(session_data.selected_files),
            "sheet_count": sum(len(sheets) for sheets in session_data.selected_sheets.values()),
            "created_at": session_data.created_at.isoformat(),
            "last_accessed": session_data.last_accessed.isoformat(),
            "age_seconds": (datetime.now() - session_data.created_at).total_seconds()
        }
    
    # =========================================================================
    # Query History Helpers
    # =========================================================================
    
    def get_last_query(self, session_id: str) -> Optional[str]:
        """
        Get the last user query from a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Last query string or None
        """
        session_data = self._load_session(session_id)
        
        if not session_data:
            return None
        
        queries = session_data.previous_queries
        return queries[-1] if queries else None
    
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
            file_id: Optional file ID (uses last file if not provided)
            
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
    
    # =========================================================================
    # Reference Resolution
    # =========================================================================
    
    def resolve_ambiguous_reference(
        self,
        query: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Resolve ambiguous references in follow-up questions.
        
        This method analyzes the query for pronouns and contextual references
        that might refer to previously discussed files, sheets, or data.
        
        Args:
            query: Current query with potential ambiguous references
            session_id: Session identifier
            
        Returns:
            Dictionary with resolved references:
            - implied_file: File ID if reference detected
            - implied_sheet: Sheet name if reference detected
            - is_follow_up: True if query appears to be a follow-up
            - previous_query: Previous query if follow-up detected
            - previous_results: Previous results if comparison detected
        """
        session_data = self._load_session(session_id)
        
        if not session_data:
            return {}
        
        resolved = {}
        query_lower = query.lower()
        
        # Check for pronouns that might refer to previous context
        pronoun_indicators = ["it", "that", "this", "same", "the file", "the sheet"]
        if any(word in query_lower for word in pronoun_indicators):
            last_file = self.get_last_selected_file(session_id)
            if last_file:
                resolved["implied_file"] = last_file
            
            last_sheet = self.get_last_selected_sheet(session_id)
            if last_sheet:
                resolved["implied_sheet"] = last_sheet
        
        # Check for follow-up indicators
        follow_up_indicators = ["also", "too", "additionally", "what about", "and", "how about"]
        if any(word in query_lower for word in follow_up_indicators):
            resolved["is_follow_up"] = True
            resolved["previous_query"] = self.get_last_query(session_id)
        
        # Check for comparison with previous results
        comparison_indicators = ["compare", "difference", "vs", "versus", "compared to"]
        if any(word in query_lower for word in comparison_indicators):
            if session_data.last_query_results:
                resolved["previous_results"] = session_data.last_query_results
        
        return resolved
    
    # =========================================================================
    # Deprecated Methods (for backward compatibility)
    # =========================================================================
    
    def list_active_sessions(self) -> List[str]:
        """
        List all active session IDs.
        
        Deprecated: Use get_all_sessions() instead for more information.
        
        Returns:
            List of active session IDs
        """
        sessions = self.get_all_sessions()
        return [s["session_id"] for s in sessions]
    
    # =========================================================================
    # Private Methods
    # =========================================================================
    
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
            ttl=self.session_timeout
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
            Cache key string
        """
        return f"{self.cache_prefix}{session_id}"
