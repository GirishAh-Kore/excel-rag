"""
Database connection management for the Google Drive Excel RAG system.

This module provides connection pooling, context managers, and utilities
for managing SQLite database connections.
"""

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from .schema import ALL_INDEXES, ALL_TABLES, ALL_TRIGGERS

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages SQLite database connections with connection pooling."""

    def __init__(self, db_path: str, check_same_thread: bool = False):
        """
        Initialize database connection manager.

        Args:
            db_path: Path to SQLite database file
            check_same_thread: Whether to check same thread (False for multi-threading)
        """
        self.db_path = db_path
        self.check_same_thread = check_same_thread
        self._connection: Optional[sqlite3.Connection] = None

        # Ensure database directory exists
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize database schema if not exists."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Create tables
                for table_sql in ALL_TABLES:
                    cursor.execute(table_sql)
                    logger.debug(f"Created/verified table")

                # Create indexes
                for index_sql in ALL_INDEXES:
                    cursor.execute(index_sql)
                    logger.debug(f"Created/verified index")

                # Create triggers
                for trigger_sql in ALL_TRIGGERS:
                    cursor.execute(trigger_sql)
                    logger.debug(f"Created/verified trigger")

                conn.commit()
                logger.info(f"Database initialized successfully at {self.db_path}")

        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _get_raw_connection(self) -> sqlite3.Connection:
        """Get or create a raw SQLite connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                check_same_thread=self.check_same_thread,
                timeout=30.0  # 30 second timeout for locks
            )
            # Enable foreign key constraints
            self._connection.execute("PRAGMA foreign_keys = ON")
            # Use WAL mode for better concurrency
            self._connection.execute("PRAGMA journal_mode = WAL")
            # Return rows as dictionaries
            self._connection.row_factory = sqlite3.Row

        return self._connection

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database connections.

        Yields:
            SQLite connection object

        Example:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM files")
        """
        conn = self._get_raw_connection()
        try:
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            conn.rollback()
            raise
        finally:
            # Don't close connection, keep it in pool
            pass

    @contextmanager
    def get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Context manager for database cursors with automatic commit.

        Yields:
            SQLite cursor object

        Example:
            with db.get_cursor() as cursor:
                cursor.execute("INSERT INTO files (...) VALUES (...)")
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Database error: {e}")
                conn.rollback()
                raise
            finally:
                cursor.close()

    def execute_query(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None
    ) -> List[sqlite3.Row]:
        """
        Execute a SELECT query and return results.

        Args:
            query: SQL query string
            params: Query parameters (optional)

        Returns:
            List of result rows as sqlite3.Row objects
        """
        with self.get_cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()

    def execute_insert(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None
    ) -> int:
        """
        Execute an INSERT query and return the last row ID.

        Args:
            query: SQL INSERT statement
            params: Query parameters (optional)

        Returns:
            Last inserted row ID
        """
        with self.get_cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.lastrowid

    def execute_update(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None
    ) -> int:
        """
        Execute an UPDATE or DELETE query and return affected rows.

        Args:
            query: SQL UPDATE/DELETE statement
            params: Query parameters (optional)

        Returns:
            Number of affected rows
        """
        with self.get_cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.rowcount

    def execute_many(
        self,
        query: str,
        params_list: List[Tuple[Any, ...]]
    ) -> int:
        """
        Execute a query multiple times with different parameters.

        Args:
            query: SQL statement
            params_list: List of parameter tuples

        Returns:
            Number of affected rows
        """
        with self.get_cursor() as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount

    def vacuum(self) -> None:
        """
        Vacuum the database to reclaim space and optimize.

        Should be called periodically for maintenance.
        """
        try:
            with self.get_connection() as conn:
                conn.execute("VACUUM")
                logger.info("Database vacuumed successfully")
        except sqlite3.Error as e:
            logger.error(f"Failed to vacuum database: {e}")
            raise

    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

    def __enter__(self) -> "DatabaseConnection":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


# Global database instance (initialized by application)
_db_instance: Optional[DatabaseConnection] = None


def initialize_database(db_path: str) -> DatabaseConnection:
    """
    Initialize the global database instance.

    Args:
        db_path: Path to SQLite database file

    Returns:
        DatabaseConnection instance
    """
    global _db_instance
    _db_instance = DatabaseConnection(db_path)
    return _db_instance


def get_database() -> DatabaseConnection:
    """
    Get the global database instance.

    Returns:
        DatabaseConnection instance

    Raises:
        RuntimeError: If database not initialized
    """
    if _db_instance is None:
        raise RuntimeError(
            "Database not initialized. Call initialize_database() first."
        )
    return _db_instance
