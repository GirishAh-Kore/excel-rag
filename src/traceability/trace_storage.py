"""
Trace Storage

This module provides CRUD operations for QueryTrace records with configurable
retention period and automatic expiration cleanup.

Key Features:
- Create, read, update, delete QueryTrace records
- Configurable retention period (default 90 days)
- Automatic trace expiration cleanup
- Efficient querying by user_id, session_id, and date range

Requirements: 16.2, 16.5
"""

import json
import logging
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.database.connection import DatabaseConnection
from src.exceptions import TraceError
from src.models.query_pipeline import (
    Citation,
    FileCandidate,
    QueryType,
    SheetCandidate,
)
from src.models.traceability import QueryTrace

logger = logging.getLogger(__name__)


# Default retention period in days
DEFAULT_RETENTION_DAYS = 90


class TraceStorage:
    """
    Manages CRUD operations for QueryTrace records in SQLite database.
    
    Provides storage and retrieval of query traces with support for
    configurable retention periods and automatic expiration cleanup.
    Uses connection pooling via the injected DatabaseConnection.
    
    Attributes:
        db_connection: Injected database connection with connection pooling.
        retention_days: Number of days to retain traces before expiration.
    
    Requirements: 16.2, 16.5
    """
    
    def __init__(
        self,
        db_connection: DatabaseConnection,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> None:
        """
        Initialize the trace storage.
        
        Args:
            db_connection: Database connection instance with connection pooling.
            retention_days: Number of days to retain traces (default 90).
        
        Raises:
            TraceError: If db_connection is None or retention_days is invalid.
        """
        if db_connection is None:
            raise TraceError(
                "Database connection is required",
                details={"parameter": "db_connection"}
            )
        if retention_days < 1:
            raise TraceError(
                "Retention days must be at least 1",
                details={"retention_days": retention_days}
            )
        
        self.db_connection = db_connection
        self.retention_days = retention_days
        logger.info(
            f"TraceStorage initialized with {retention_days} day retention"
        )

    def create_trace(self, trace: QueryTrace) -> str:
        """
        Create a new QueryTrace record.
        
        Args:
            trace: QueryTrace object containing trace data.
        
        Returns:
            The trace_id of the created trace.
        
        Raises:
            TraceError: If trace creation fails.
        
        Requirements: 16.2
        """
        try:
            expires_at = datetime.now() + timedelta(days=self.retention_days)
            
            query = """
                INSERT INTO query_traces (
                    trace_id, query_text, user_id, session_id,
                    file_selection_json, sheet_selection_json,
                    query_type, classification_confidence,
                    chunks_retrieved, answer_text, citations_json,
                    answer_confidence, total_processing_time_ms,
                    created_at, expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # Serialize complex fields to JSON
            file_selection_json = self._serialize_file_selection(trace)
            sheet_selection_json = self._serialize_sheet_selection(trace)
            citations_json = self._serialize_citations(trace.citations)
            chunks_json = json.dumps(trace.chunks_retrieved)
            
            params = (
                trace.trace_id,
                trace.query_text,
                trace.user_id,
                trace.session_id,
                file_selection_json,
                sheet_selection_json,
                trace.query_type.value if trace.query_type else None,
                trace.classification_confidence,
                chunks_json,
                trace.answer_text,
                citations_json,
                trace.answer_confidence,
                trace.total_processing_time_ms,
                trace.timestamp,
                expires_at.isoformat(),
            )
            
            self.db_connection.execute_insert(query, params)
            logger.debug(f"Created trace: {trace.trace_id}")
            return trace.trace_id
            
        except Exception as e:
            logger.error(f"Failed to create trace: {e}", exc_info=True)
            raise TraceError(
                f"Failed to create trace: {e}",
                details={"trace_id": trace.trace_id}
            )

    def get_trace(self, trace_id: str) -> Optional[QueryTrace]:
        """
        Retrieve a QueryTrace by its ID.
        
        Args:
            trace_id: Unique identifier of the trace.
        
        Returns:
            QueryTrace object or None if not found.
        
        Raises:
            TraceError: If retrieval fails.
        
        Requirements: 16.2
        """
        try:
            query = """
                SELECT 
                    trace_id, query_text, user_id, session_id,
                    file_selection_json, sheet_selection_json,
                    query_type, classification_confidence,
                    chunks_retrieved, answer_text, citations_json,
                    answer_confidence, total_processing_time_ms,
                    created_at, expires_at
                FROM query_traces
                WHERE trace_id = ?
            """
            
            results = self.db_connection.execute_query(query, (trace_id,))
            
            if not results:
                return None
            
            row = dict(results[0])
            return self._row_to_trace(row)
            
        except Exception as e:
            logger.error(f"Failed to get trace: {e}", exc_info=True)
            raise TraceError(
                f"Failed to get trace: {e}",
                details={"trace_id": trace_id}
            )

    def update_trace(self, trace: QueryTrace) -> bool:
        """
        Update an existing QueryTrace record.
        
        Args:
            trace: QueryTrace object with updated data.
        
        Returns:
            True if update was successful, False if trace not found.
        
        Raises:
            TraceError: If update fails.
        """
        try:
            query = """
                UPDATE query_traces SET
                    query_text = ?,
                    file_selection_json = ?,
                    sheet_selection_json = ?,
                    query_type = ?,
                    classification_confidence = ?,
                    chunks_retrieved = ?,
                    answer_text = ?,
                    citations_json = ?,
                    answer_confidence = ?,
                    total_processing_time_ms = ?
                WHERE trace_id = ?
            """
            
            file_selection_json = self._serialize_file_selection(trace)
            sheet_selection_json = self._serialize_sheet_selection(trace)
            citations_json = self._serialize_citations(trace.citations)
            chunks_json = json.dumps(trace.chunks_retrieved)
            
            params = (
                trace.query_text,
                file_selection_json,
                sheet_selection_json,
                trace.query_type.value if trace.query_type else None,
                trace.classification_confidence,
                chunks_json,
                trace.answer_text,
                citations_json,
                trace.answer_confidence,
                trace.total_processing_time_ms,
                trace.trace_id,
            )
            
            rows_affected = self.db_connection.execute_update(query, params)
            
            if rows_affected > 0:
                logger.debug(f"Updated trace: {trace.trace_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to update trace: {e}", exc_info=True)
            raise TraceError(
                f"Failed to update trace: {e}",
                details={"trace_id": trace.trace_id}
            )

    def delete_trace(self, trace_id: str) -> bool:
        """
        Delete a QueryTrace record.
        
        Args:
            trace_id: Unique identifier of the trace to delete.
        
        Returns:
            True if deletion was successful, False if trace not found.
        
        Raises:
            TraceError: If deletion fails.
        """
        try:
            query = "DELETE FROM query_traces WHERE trace_id = ?"
            rows_affected = self.db_connection.execute_update(query, (trace_id,))
            
            if rows_affected > 0:
                logger.debug(f"Deleted trace: {trace_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete trace: {e}", exc_info=True)
            raise TraceError(
                f"Failed to delete trace: {e}",
                details={"trace_id": trace_id}
            )

    def get_traces_by_user(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[QueryTrace]:
        """
        Retrieve traces for a specific user.
        
        Args:
            user_id: User identifier to filter by.
            limit: Maximum number of traces to return.
            offset: Number of traces to skip.
        
        Returns:
            List of QueryTrace objects ordered by creation time descending.
        
        Raises:
            TraceError: If retrieval fails.
        """
        try:
            query = """
                SELECT 
                    trace_id, query_text, user_id, session_id,
                    file_selection_json, sheet_selection_json,
                    query_type, classification_confidence,
                    chunks_retrieved, answer_text, citations_json,
                    answer_confidence, total_processing_time_ms,
                    created_at, expires_at
                FROM query_traces
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            
            results = self.db_connection.execute_query(
                query, (user_id, limit, offset)
            )
            return [self._row_to_trace(dict(row)) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get traces by user: {e}", exc_info=True)
            raise TraceError(
                f"Failed to get traces by user: {e}",
                details={"user_id": user_id}
            )

    def get_traces_by_session(
        self,
        session_id: str,
        limit: int = 100,
    ) -> List[QueryTrace]:
        """
        Retrieve traces for a specific session.
        
        Args:
            session_id: Session identifier to filter by.
            limit: Maximum number of traces to return.
        
        Returns:
            List of QueryTrace objects ordered by creation time ascending.
        
        Raises:
            TraceError: If retrieval fails.
        """
        try:
            query = """
                SELECT 
                    trace_id, query_text, user_id, session_id,
                    file_selection_json, sheet_selection_json,
                    query_type, classification_confidence,
                    chunks_retrieved, answer_text, citations_json,
                    answer_confidence, total_processing_time_ms,
                    created_at, expires_at
                FROM query_traces
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            """
            
            results = self.db_connection.execute_query(
                query, (session_id, limit)
            )
            return [self._row_to_trace(dict(row)) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get traces by session: {e}", exc_info=True)
            raise TraceError(
                f"Failed to get traces by session: {e}",
                details={"session_id": session_id}
            )

    def get_traces_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 1000,
    ) -> List[QueryTrace]:
        """
        Retrieve traces within a date range.
        
        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).
            limit: Maximum number of traces to return.
        
        Returns:
            List of QueryTrace objects ordered by creation time descending.
        
        Raises:
            TraceError: If retrieval fails.
        """
        try:
            query = """
                SELECT 
                    trace_id, query_text, user_id, session_id,
                    file_selection_json, sheet_selection_json,
                    query_type, classification_confidence,
                    chunks_retrieved, answer_text, citations_json,
                    answer_confidence, total_processing_time_ms,
                    created_at, expires_at
                FROM query_traces
                WHERE created_at >= ? AND created_at <= ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            
            results = self.db_connection.execute_query(
                query,
                (start_date.isoformat(), end_date.isoformat(), limit)
            )
            return [self._row_to_trace(dict(row)) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get traces by date range: {e}", exc_info=True)
            raise TraceError(
                f"Failed to get traces by date range: {e}",
                details={"start_date": start_date, "end_date": end_date}
            )

    def cleanup_expired_traces(self) -> int:
        """
        Delete all expired traces based on retention period.
        
        Returns:
            Number of traces deleted.
        
        Raises:
            TraceError: If cleanup fails.
        
        Requirements: 16.5
        """
        try:
            now = datetime.now().isoformat()
            
            query = "DELETE FROM query_traces WHERE expires_at < ?"
            rows_affected = self.db_connection.execute_update(query, (now,))
            
            if rows_affected > 0:
                logger.info(f"Cleaned up {rows_affected} expired traces")
            
            return rows_affected
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired traces: {e}", exc_info=True)
            raise TraceError(
                f"Failed to cleanup expired traces: {e}",
                details={}
            )

    def get_trace_count(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """
        Get the count of traces, optionally filtered.
        
        Args:
            user_id: Optional user ID to filter by.
            session_id: Optional session ID to filter by.
        
        Returns:
            Number of traces matching the criteria.
        
        Raises:
            TraceError: If count fails.
        """
        try:
            clauses: List[str] = []
            params: List[Any] = []
            
            if user_id is not None:
                clauses.append("user_id = ?")
                params.append(user_id)
            
            if session_id is not None:
                clauses.append("session_id = ?")
                params.append(session_id)
            
            where_clause = " AND ".join(clauses) if clauses else "1=1"
            query = f"SELECT COUNT(*) as count FROM query_traces WHERE {where_clause}"
            
            results = self.db_connection.execute_query(query, tuple(params))
            return results[0]["count"] if results else 0
            
        except Exception as e:
            logger.error(f"Failed to get trace count: {e}", exc_info=True)
            raise TraceError(
                f"Failed to get trace count: {e}",
                details={"user_id": user_id, "session_id": session_id}
            )

    def get_expired_trace_count(self) -> int:
        """
        Get the count of expired traces pending cleanup.
        
        Returns:
            Number of expired traces.
        
        Raises:
            TraceError: If count fails.
        """
        try:
            now = datetime.now().isoformat()
            query = "SELECT COUNT(*) as count FROM query_traces WHERE expires_at < ?"
            
            results = self.db_connection.execute_query(query, (now,))
            return results[0]["count"] if results else 0
            
        except Exception as e:
            logger.error(f"Failed to get expired trace count: {e}", exc_info=True)
            raise TraceError(
                f"Failed to get expired trace count: {e}",
                details={}
            )

    def extend_trace_retention(
        self,
        trace_id: str,
        additional_days: int,
    ) -> bool:
        """
        Extend the retention period for a specific trace.
        
        Args:
            trace_id: Unique identifier of the trace.
            additional_days: Number of days to extend retention.
        
        Returns:
            True if extension was successful, False if trace not found.
        
        Raises:
            TraceError: If extension fails.
        """
        try:
            query = """
                UPDATE query_traces
                SET expires_at = datetime(expires_at, '+' || ? || ' days')
                WHERE trace_id = ?
            """
            
            rows_affected = self.db_connection.execute_update(
                query, (additional_days, trace_id)
            )
            
            if rows_affected > 0:
                logger.debug(
                    f"Extended retention for trace {trace_id} by {additional_days} days"
                )
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to extend trace retention: {e}", exc_info=True)
            raise TraceError(
                f"Failed to extend trace retention: {e}",
                details={"trace_id": trace_id, "additional_days": additional_days}
            )

    def _serialize_file_selection(self, trace: QueryTrace) -> str:
        """Serialize file selection data to JSON."""
        data = {
            "candidates": [
                {
                    "file_id": c.file_id,
                    "file_name": c.file_name,
                    "semantic_score": c.semantic_score,
                    "metadata_score": c.metadata_score,
                    "preference_score": c.preference_score,
                    "combined_score": c.combined_score,
                    "rejection_reason": c.rejection_reason,
                }
                for c in trace.file_candidates
            ],
            "selected_file_id": trace.selected_file_id,
            "reasoning": trace.file_selection_reasoning,
            "confidence": trace.file_confidence,
            "time_ms": trace.file_selection_time_ms,
        }
        return json.dumps(data)

    def _serialize_sheet_selection(self, trace: QueryTrace) -> str:
        """Serialize sheet selection data to JSON."""
        data = {
            "candidates": [
                {
                    "sheet_name": c.sheet_name,
                    "name_score": c.name_score,
                    "header_score": c.header_score,
                    "data_type_score": c.data_type_score,
                    "content_score": c.content_score,
                    "combined_score": c.combined_score,
                }
                for c in trace.sheet_candidates
            ],
            "selected_sheets": trace.selected_sheets,
            "reasoning": trace.sheet_selection_reasoning,
            "confidence": trace.sheet_confidence,
            "time_ms": trace.sheet_selection_time_ms,
        }
        return json.dumps(data)

    def _serialize_citations(self, citations: List[Citation]) -> str:
        """Serialize citations to JSON."""
        data = [
            {
                "file_name": c.file_name,
                "sheet_name": c.sheet_name,
                "cell_range": c.cell_range,
                "lineage_id": c.lineage_id,
                "source_value": c.source_value,
            }
            for c in citations
        ]
        return json.dumps(data)

    def _row_to_trace(self, row: Dict[str, Any]) -> QueryTrace:
        """Convert a database row to a QueryTrace object."""
        # Parse file selection JSON
        file_selection = json.loads(row.get("file_selection_json") or "{}")
        file_candidates = [
            FileCandidate(
                file_id=c.get("file_id", ""),
                file_name=c.get("file_name", ""),
                semantic_score=c.get("semantic_score", 0.0),
                metadata_score=c.get("metadata_score", 0.0),
                preference_score=c.get("preference_score", 0.0),
                combined_score=c.get("combined_score", 0.0),
                rejection_reason=c.get("rejection_reason"),
            )
            for c in file_selection.get("candidates", [])
        ]
        
        # Parse sheet selection JSON
        sheet_selection = json.loads(row.get("sheet_selection_json") or "{}")
        sheet_candidates = [
            SheetCandidate(
                sheet_name=c.get("sheet_name", ""),
                name_score=c.get("name_score", 0.0),
                header_score=c.get("header_score", 0.0),
                data_type_score=c.get("data_type_score", 0.0),
                content_score=c.get("content_score", 0.0),
                combined_score=c.get("combined_score", 0.0),
            )
            for c in sheet_selection.get("candidates", [])
        ]
        
        # Parse citations JSON
        citations_data = json.loads(row.get("citations_json") or "[]")
        citations = [
            Citation(
                file_name=c.get("file_name", ""),
                sheet_name=c.get("sheet_name", ""),
                cell_range=c.get("cell_range", ""),
                lineage_id=c.get("lineage_id", ""),
                source_value=c.get("source_value"),
            )
            for c in citations_data
        ]
        
        # Parse chunks retrieved
        chunks = json.loads(row.get("chunks_retrieved") or "[]")
        
        # Parse query type
        query_type_str = row.get("query_type")
        query_type = QueryType(query_type_str) if query_type_str else None
        
        return QueryTrace(
            trace_id=row["trace_id"],
            query_text=row["query_text"],
            timestamp=row.get("created_at", ""),
            user_id=row.get("user_id"),
            session_id=row.get("session_id"),
            file_candidates=file_candidates,
            file_selection_reasoning=file_selection.get("reasoning", ""),
            selected_file_id=file_selection.get("selected_file_id", ""),
            file_confidence=file_selection.get("confidence", 0.0),
            sheet_candidates=sheet_candidates,
            sheet_selection_reasoning=sheet_selection.get("reasoning", ""),
            selected_sheets=sheet_selection.get("selected_sheets", []),
            sheet_confidence=sheet_selection.get("confidence", 0.0),
            query_type=query_type,
            classification_confidence=row.get("classification_confidence", 0.0),
            chunks_retrieved=chunks,
            retrieval_scores=[],
            answer_text=row.get("answer_text", ""),
            citations=citations,
            answer_confidence=row.get("answer_confidence", 0.0),
            total_processing_time_ms=row.get("total_processing_time_ms", 0),
            file_selection_time_ms=file_selection.get("time_ms", 0),
            sheet_selection_time_ms=sheet_selection.get("time_ms", 0),
            retrieval_time_ms=0,
            generation_time_ms=0,
        )
