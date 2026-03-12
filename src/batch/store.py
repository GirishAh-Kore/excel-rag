"""
Batch Query Store Module.

This module implements storage for batch query status and results
using the SQLite database.

Supports Requirements 24.1, 24.5.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from src.database.connection import DatabaseConnection
from src.models.enterprise import BatchQueryStatus

logger = logging.getLogger(__name__)


class BatchQueryStore:
    """
    Storage for batch query status and results.
    
    Provides persistence for batch processing state, enabling
    progress tracking and result retrieval.
    
    All dependencies are injected via constructor following DIP.
    
    Example:
        >>> store = BatchQueryStore(db=database_connection)
        >>> store.create_batch("batch_123", total_queries=10)
        >>> store.update_batch_progress("batch_123", completed=5, failed=0, status="processing")
    """
    
    # SQL statements
    CREATE_BATCH_SQL = """
        INSERT INTO batch_queries (batch_id, total_queries, completed, failed, status, user_id, created_at)
        VALUES (?, ?, 0, 0, 'pending', ?, ?)
    """
    
    UPDATE_PROGRESS_SQL = """
        UPDATE batch_queries
        SET completed = ?, failed = ?, status = ?, updated_at = ?
        WHERE batch_id = ?
    """
    
    STORE_RESULTS_SQL = """
        UPDATE batch_queries
        SET results = ?, updated_at = ?
        WHERE batch_id = ?
    """
    
    GET_STATUS_SQL = """
        SELECT batch_id, total_queries, completed, failed, status, results
        FROM batch_queries
        WHERE batch_id = ?
    """
    
    def __init__(self, db: DatabaseConnection) -> None:
        """
        Initialize BatchQueryStore with database connection.
        
        Args:
            db: Database connection for persistence.
            
        Raises:
            ValueError: If db is None.
        """
        if db is None:
            raise ValueError("db is required")
        
        self._db = db
        self._ensure_table_exists()
        
        logger.info("BatchQueryStore initialized")
    
    def _ensure_table_exists(self) -> None:
        """Ensure the batch_queries table exists."""
        create_table_sql = """
            CREATE TABLE IF NOT EXISTS batch_queries (
                batch_id TEXT PRIMARY KEY,
                total_queries INTEGER NOT NULL,
                completed INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                results TEXT,
                user_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """
        
        create_index_sql = """
            CREATE INDEX IF NOT EXISTS idx_batch_queries_status 
            ON batch_queries(status)
        """
        
        try:
            with self._db.get_cursor() as cursor:
                cursor.execute(create_table_sql)
                cursor.execute(create_index_sql)
        except Exception as e:
            logger.error(f"Failed to create batch_queries table: {e}")
            raise
    
    def create_batch(
        self,
        batch_id: str,
        total_queries: int,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Create a new batch record.
        
        Args:
            batch_id: Unique batch identifier.
            total_queries: Total number of queries in batch.
            user_id: Optional user ID.
            
        Returns:
            True if created successfully.
        """
        try:
            now = datetime.utcnow().isoformat()
            self._db.execute_insert(
                self.CREATE_BATCH_SQL,
                (batch_id, total_queries, user_id, now)
            )
            logger.debug(f"Created batch record: {batch_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create batch {batch_id}: {e}")
            return False
    
    def update_batch_progress(
        self,
        batch_id: str,
        completed: int,
        failed: int,
        status: str
    ) -> bool:
        """
        Update batch progress.
        
        Args:
            batch_id: Unique batch identifier.
            completed: Number of completed queries.
            failed: Number of failed queries.
            status: Current batch status.
            
        Returns:
            True if updated successfully.
        """
        try:
            now = datetime.utcnow().isoformat()
            rows_affected = self._db.execute_update(
                self.UPDATE_PROGRESS_SQL,
                (completed, failed, status, now, batch_id)
            )
            return rows_affected > 0
        except Exception as e:
            logger.error(f"Failed to update batch {batch_id}: {e}")
            return False
    
    def store_batch_results(
        self,
        batch_id: str,
        results: list[dict[str, Any]]
    ) -> bool:
        """
        Store batch results.
        
        Args:
            batch_id: Unique batch identifier.
            results: List of query results.
            
        Returns:
            True if stored successfully.
        """
        try:
            now = datetime.utcnow().isoformat()
            results_json = json.dumps(results)
            rows_affected = self._db.execute_update(
                self.STORE_RESULTS_SQL,
                (results_json, now, batch_id)
            )
            return rows_affected > 0
        except Exception as e:
            logger.error(f"Failed to store results for batch {batch_id}: {e}")
            return False
    
    def get_batch_status(self, batch_id: str) -> Optional[BatchQueryStatus]:
        """
        Get batch status by ID.
        
        Args:
            batch_id: Unique batch identifier.
            
        Returns:
            BatchQueryStatus if found, None otherwise.
        """
        try:
            rows = self._db.execute_query(
                self.GET_STATUS_SQL,
                (batch_id,)
            )
            
            if not rows:
                return None
            
            row = rows[0]
            results = None
            if row["results"]:
                results = json.loads(row["results"])
            
            return BatchQueryStatus(
                batch_id=row["batch_id"],
                total_queries=row["total_queries"],
                completed=row["completed"],
                failed=row["failed"],
                status=row["status"],
                results=results
            )
        except Exception as e:
            logger.error(f"Failed to get batch status {batch_id}: {e}")
            return None
