"""
Export Store Module.

This module implements storage for scheduled exports using SQLite.

Key Features:
- CRUD operations for scheduled exports
- Query due schedules for execution
- User-based schedule retrieval

Supports Requirement 26.5: Support scheduled exports for recurring reports.
"""

import json
import logging
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from src.export.service import (
    ExportFormat,
    ScheduledExport,
    ScheduleFrequency,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Protocols
# =============================================================================


@runtime_checkable
class DatabaseConnectionProtocol(Protocol):
    """
    Protocol for database connection.
    
    Implementations must provide methods for executing queries.
    """
    
    def execute_query(
        self,
        query: str,
        params: tuple = ()
    ) -> list[dict]:
        """Execute a SELECT query and return results."""
        ...
    
    def execute_insert(
        self,
        query: str,
        params: tuple = ()
    ) -> int:
        """Execute an INSERT query and return last row ID."""
        ...
    
    def execute_update(
        self,
        query: str,
        params: tuple = ()
    ) -> int:
        """Execute an UPDATE/DELETE query and return affected rows."""
        ...


# =============================================================================
# SQL Statements
# =============================================================================

CREATE_SCHEDULED_EXPORTS_TABLE = """
CREATE TABLE IF NOT EXISTS scheduled_exports (
    schedule_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    query_or_result_id TEXT NOT NULL,
    export_format TEXT NOT NULL,
    frequency TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    destination TEXT
);
"""

CREATE_SCHEDULED_EXPORTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_scheduled_exports_created_by ON scheduled_exports(created_by);",
    "CREATE INDEX IF NOT EXISTS idx_scheduled_exports_next_run ON scheduled_exports(next_run_at);",
    "CREATE INDEX IF NOT EXISTS idx_scheduled_exports_active ON scheduled_exports(is_active);",
]


# =============================================================================
# Export Store
# =============================================================================


class ExportStore:
    """
    SQLite-based storage for scheduled exports.
    
    Provides CRUD operations for scheduled export configurations
    and supports querying for due schedules.
    
    All dependencies are injected via constructor following DIP.
    
    Implements Requirement 26.5: Support scheduled exports for recurring reports.
    
    Example:
        >>> store = ExportStore(db_connection=db)
        >>> store.create_schedule(schedule)
        >>> due_schedules = store.get_due_schedules(datetime.utcnow())
    """
    
    def __init__(self, db_connection: DatabaseConnectionProtocol) -> None:
        """
        Initialize ExportStore with injected database connection.
        
        Args:
            db_connection: Database connection for storage operations.
            
        Raises:
            ValueError: If db_connection is None.
        """
        if db_connection is None:
            raise ValueError("db_connection is required")
        
        self._db = db_connection
        self._ensure_table_exists()
        
        logger.info("ExportStore initialized")
    
    def _ensure_table_exists(self) -> None:
        """Create the scheduled_exports table if it doesn't exist."""
        try:
            # Use execute_query for DDL since it doesn't return rows
            self._db.execute_query(CREATE_SCHEDULED_EXPORTS_TABLE)
            for index_sql in CREATE_SCHEDULED_EXPORTS_INDEXES:
                self._db.execute_query(index_sql)
        except Exception as e:
            logger.warning(f"Could not create scheduled_exports table: {e}")
    
    def create_schedule(self, schedule: ScheduledExport) -> bool:
        """
        Create a new scheduled export.
        
        Args:
            schedule: ScheduledExport to create.
            
        Returns:
            True if created successfully, False otherwise.
        """
        query = """
        INSERT INTO scheduled_exports (
            schedule_id, name, query_or_result_id, export_format,
            frequency, created_by, created_at, last_run_at,
            next_run_at, is_active, destination
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            schedule.schedule_id,
            schedule.name,
            schedule.query_or_result_id,
            schedule.export_format.value,
            schedule.frequency.value,
            schedule.created_by,
            schedule.created_at.isoformat(),
            schedule.last_run_at.isoformat() if schedule.last_run_at else None,
            schedule.next_run_at.isoformat() if schedule.next_run_at else None,
            1 if schedule.is_active else 0,
            schedule.destination
        )
        
        try:
            self._db.execute_insert(query, params)
            logger.debug(f"Created scheduled export: {schedule.schedule_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create scheduled export: {e}")
            return False
    
    def get_schedule(self, schedule_id: str) -> Optional[ScheduledExport]:
        """
        Get a scheduled export by ID.
        
        Args:
            schedule_id: Unique schedule identifier.
            
        Returns:
            ScheduledExport if found, None otherwise.
        """
        query = """
        SELECT schedule_id, name, query_or_result_id, export_format,
               frequency, created_by, created_at, last_run_at,
               next_run_at, is_active, destination
        FROM scheduled_exports
        WHERE schedule_id = ?
        """
        
        try:
            results = self._db.execute_query(query, (schedule_id,))
            if not results:
                return None
            
            return self._row_to_schedule(results[0])
        except Exception as e:
            logger.error(f"Failed to get scheduled export {schedule_id}: {e}")
            return None
    
    def get_schedules_for_user(self, user_id: str) -> list[ScheduledExport]:
        """
        Get all scheduled exports for a user.
        
        Args:
            user_id: User ID to get schedules for.
            
        Returns:
            List of ScheduledExport objects.
        """
        query = """
        SELECT schedule_id, name, query_or_result_id, export_format,
               frequency, created_by, created_at, last_run_at,
               next_run_at, is_active, destination
        FROM scheduled_exports
        WHERE created_by = ?
        ORDER BY created_at DESC
        """
        
        try:
            results = self._db.execute_query(query, (user_id,))
            return [self._row_to_schedule(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to get schedules for user {user_id}: {e}")
            return []
    
    def get_due_schedules(self, as_of: datetime) -> list[ScheduledExport]:
        """
        Get all schedules due for execution.
        
        Args:
            as_of: Reference time for determining due schedules.
            
        Returns:
            List of ScheduledExport objects due for execution.
        """
        query = """
        SELECT schedule_id, name, query_or_result_id, export_format,
               frequency, created_by, created_at, last_run_at,
               next_run_at, is_active, destination
        FROM scheduled_exports
        WHERE is_active = 1
          AND next_run_at IS NOT NULL
          AND next_run_at <= ?
        ORDER BY next_run_at ASC
        """
        
        try:
            results = self._db.execute_query(query, (as_of.isoformat(),))
            return [self._row_to_schedule(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to get due schedules: {e}")
            return []
    
    def update_schedule(self, schedule: ScheduledExport) -> bool:
        """
        Update a scheduled export.
        
        Args:
            schedule: ScheduledExport with updated values.
            
        Returns:
            True if updated successfully, False otherwise.
        """
        query = """
        UPDATE scheduled_exports
        SET name = ?,
            export_format = ?,
            frequency = ?,
            last_run_at = ?,
            next_run_at = ?,
            is_active = ?,
            destination = ?
        WHERE schedule_id = ?
        """
        
        params = (
            schedule.name,
            schedule.export_format.value,
            schedule.frequency.value,
            schedule.last_run_at.isoformat() if schedule.last_run_at else None,
            schedule.next_run_at.isoformat() if schedule.next_run_at else None,
            1 if schedule.is_active else 0,
            schedule.destination,
            schedule.schedule_id
        )
        
        try:
            affected = self._db.execute_update(query, params)
            if affected > 0:
                logger.debug(f"Updated scheduled export: {schedule.schedule_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to update scheduled export: {e}")
            return False
    
    def delete_schedule(self, schedule_id: str) -> bool:
        """
        Delete a scheduled export.
        
        Args:
            schedule_id: ID of the schedule to delete.
            
        Returns:
            True if deleted successfully, False otherwise.
        """
        query = "DELETE FROM scheduled_exports WHERE schedule_id = ?"
        
        try:
            affected = self._db.execute_update(query, (schedule_id,))
            if affected > 0:
                logger.debug(f"Deleted scheduled export: {schedule_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete scheduled export: {e}")
            return False
    
    def _row_to_schedule(self, row: dict) -> ScheduledExport:
        """
        Convert a database row to a ScheduledExport object.
        
        Args:
            row: Database row as dictionary.
            
        Returns:
            ScheduledExport object.
        """
        return ScheduledExport(
            schedule_id=row["schedule_id"],
            name=row["name"],
            query_or_result_id=row["query_or_result_id"],
            export_format=ExportFormat(row["export_format"]),
            frequency=ScheduleFrequency(row["frequency"]),
            created_by=row["created_by"],
            created_at=self._parse_datetime(row["created_at"]),
            last_run_at=self._parse_datetime(row["last_run_at"]),
            next_run_at=self._parse_datetime(row["next_run_at"]),
            is_active=bool(row["is_active"]),
            destination=row["destination"]
        )
    
    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """
        Parse a datetime string from the database.
        
        Args:
            value: ISO format datetime string or None.
            
        Returns:
            datetime object or None.
        """
        if value is None:
            return None
        
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None
