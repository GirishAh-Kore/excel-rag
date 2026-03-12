"""
Lineage Storage

This module provides CRUD operations for DataLineage records, enabling
tracking of data flow from source Excel cells to answer components.

Key Features:
- Create, read, update, delete DataLineage records
- Link answer components to source cells
- Query lineage by trace_id, file_id, or chunk_id
- Support staleness tracking

Requirements: 17.1, 17.3
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.database.connection import DatabaseConnection
from src.exceptions import LineageError
from src.models.traceability import DataLineage

logger = logging.getLogger(__name__)


class LineageStorage:
    """
    Manages CRUD operations for DataLineage records in SQLite database.
    
    Provides storage and retrieval of data lineage records that link
    answer components to their source cells in Excel files. Uses
    connection pooling via the injected DatabaseConnection.
    
    Attributes:
        db_connection: Injected database connection with connection pooling.
    
    Requirements: 17.1, 17.3
    """
    
    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize the lineage storage.
        
        Args:
            db_connection: Database connection instance with connection pooling.
        
        Raises:
            LineageError: If db_connection is None.
        """
        if db_connection is None:
            raise LineageError(
                "Database connection is required",
                details={"parameter": "db_connection"}
            )
        
        self.db_connection = db_connection
        logger.info("LineageStorage initialized")

    def create_lineage(self, lineage: DataLineage, trace_id: str) -> str:
        """
        Create a new DataLineage record.
        
        Args:
            lineage: DataLineage object containing lineage data.
            trace_id: The trace ID this lineage belongs to.
        
        Returns:
            The lineage_id of the created record.
        
        Raises:
            LineageError: If lineage creation fails.
        
        Requirements: 17.1
        """
        try:
            query = """
                INSERT INTO data_lineage (
                    lineage_id, trace_id, answer_component, file_id,
                    sheet_name, cell_range, source_value, chunk_id,
                    embedding_id, retrieval_score, indexed_at,
                    last_verified_at, is_stale, stale_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                lineage.lineage_id,
                trace_id,
                lineage.answer_component,
                lineage.file_id,
                lineage.sheet_name,
                lineage.cell_range,
                lineage.source_value,
                lineage.chunk_id,
                lineage.embedding_id,
                lineage.retrieval_score,
                lineage.indexed_at,
                lineage.last_verified_at,
                lineage.is_stale,
                lineage.stale_reason,
            )
            
            self.db_connection.execute_insert(query, params)
            logger.debug(f"Created lineage: {lineage.lineage_id}")
            return lineage.lineage_id
            
        except Exception as e:
            logger.error(f"Failed to create lineage: {e}", exc_info=True)
            raise LineageError(
                f"Failed to create lineage: {e}",
                details={"lineage_id": lineage.lineage_id}
            )

    def get_lineage(self, lineage_id: str) -> Optional[DataLineage]:
        """
        Retrieve a DataLineage record by its ID.
        
        Args:
            lineage_id: Unique identifier of the lineage record.
        
        Returns:
            DataLineage object or None if not found.
        
        Raises:
            LineageError: If retrieval fails.
        
        Requirements: 17.3
        """
        try:
            query = """
                SELECT 
                    dl.lineage_id, dl.answer_component, dl.file_id,
                    f.name as file_name, dl.sheet_name, dl.cell_range,
                    dl.source_value, dl.chunk_id, dl.embedding_id,
                    dl.retrieval_score, dl.indexed_at, dl.last_verified_at,
                    dl.is_stale, dl.stale_reason
                FROM data_lineage dl
                LEFT JOIN files f ON dl.file_id = f.file_id
                WHERE dl.lineage_id = ?
            """
            
            results = self.db_connection.execute_query(query, (lineage_id,))
            
            if not results:
                return None
            
            row = dict(results[0])
            return self._row_to_lineage(row)
            
        except Exception as e:
            logger.error(f"Failed to get lineage: {e}", exc_info=True)
            raise LineageError(
                f"Failed to get lineage: {e}",
                details={"lineage_id": lineage_id}
            )

    def get_lineages_by_trace(self, trace_id: str) -> List[DataLineage]:
        """
        Retrieve all lineage records for a specific trace.
        
        Args:
            trace_id: The trace identifier.
        
        Returns:
            List of DataLineage objects.
        
        Raises:
            LineageError: If retrieval fails.
        """
        try:
            query = """
                SELECT 
                    dl.lineage_id, dl.answer_component, dl.file_id,
                    f.name as file_name, dl.sheet_name, dl.cell_range,
                    dl.source_value, dl.chunk_id, dl.embedding_id,
                    dl.retrieval_score, dl.indexed_at, dl.last_verified_at,
                    dl.is_stale, dl.stale_reason
                FROM data_lineage dl
                LEFT JOIN files f ON dl.file_id = f.file_id
                WHERE dl.trace_id = ?
                ORDER BY dl.lineage_id
            """
            
            results = self.db_connection.execute_query(query, (trace_id,))
            return [self._row_to_lineage(dict(row)) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get lineages by trace: {e}", exc_info=True)
            raise LineageError(
                f"Failed to get lineages by trace: {e}",
                details={"trace_id": trace_id}
            )

    def get_lineages_by_file(self, file_id: str) -> List[DataLineage]:
        """
        Retrieve all lineage records for a specific file.
        
        Args:
            file_id: The file identifier.
        
        Returns:
            List of DataLineage objects.
        
        Raises:
            LineageError: If retrieval fails.
        """
        try:
            query = """
                SELECT 
                    dl.lineage_id, dl.answer_component, dl.file_id,
                    f.name as file_name, dl.sheet_name, dl.cell_range,
                    dl.source_value, dl.chunk_id, dl.embedding_id,
                    dl.retrieval_score, dl.indexed_at, dl.last_verified_at,
                    dl.is_stale, dl.stale_reason
                FROM data_lineage dl
                LEFT JOIN files f ON dl.file_id = f.file_id
                WHERE dl.file_id = ?
                ORDER BY dl.lineage_id
            """
            
            results = self.db_connection.execute_query(query, (file_id,))
            return [self._row_to_lineage(dict(row)) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get lineages by file: {e}", exc_info=True)
            raise LineageError(
                f"Failed to get lineages by file: {e}",
                details={"file_id": file_id}
            )

    def get_lineages_by_chunk(self, chunk_id: str) -> List[DataLineage]:
        """
        Retrieve all lineage records for a specific chunk.
        
        Args:
            chunk_id: The chunk identifier.
        
        Returns:
            List of DataLineage objects.
        
        Raises:
            LineageError: If retrieval fails.
        """
        try:
            query = """
                SELECT 
                    dl.lineage_id, dl.answer_component, dl.file_id,
                    f.name as file_name, dl.sheet_name, dl.cell_range,
                    dl.source_value, dl.chunk_id, dl.embedding_id,
                    dl.retrieval_score, dl.indexed_at, dl.last_verified_at,
                    dl.is_stale, dl.stale_reason
                FROM data_lineage dl
                LEFT JOIN files f ON dl.file_id = f.file_id
                WHERE dl.chunk_id = ?
                ORDER BY dl.lineage_id
            """
            
            results = self.db_connection.execute_query(query, (chunk_id,))
            return [self._row_to_lineage(dict(row)) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get lineages by chunk: {e}", exc_info=True)
            raise LineageError(
                f"Failed to get lineages by chunk: {e}",
                details={"chunk_id": chunk_id}
            )

    def update_lineage(
        self,
        lineage_id: str,
        updates: Dict[str, Any],
    ) -> bool:
        """
        Update an existing DataLineage record.
        
        Args:
            lineage_id: Unique identifier of the lineage to update.
            updates: Dictionary of fields to update.
        
        Returns:
            True if update was successful, False if lineage not found.
        
        Raises:
            LineageError: If update fails.
        """
        if not updates:
            return True
        
        # Allowed fields for update
        allowed_fields = {
            "last_verified_at", "is_stale", "stale_reason",
            "source_value", "retrieval_score"
        }
        
        # Filter to only allowed fields
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not filtered_updates:
            logger.warning(f"No valid fields to update for lineage {lineage_id}")
            return True
        
        try:
            set_clauses = [f"{field} = ?" for field in filtered_updates.keys()]
            set_clause = ", ".join(set_clauses)
            
            query = f"UPDATE data_lineage SET {set_clause} WHERE lineage_id = ?"
            params = tuple(filtered_updates.values()) + (lineage_id,)
            
            rows_affected = self.db_connection.execute_update(query, params)
            
            if rows_affected > 0:
                logger.debug(f"Updated lineage: {lineage_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to update lineage: {e}", exc_info=True)
            raise LineageError(
                f"Failed to update lineage: {e}",
                details={"lineage_id": lineage_id}
            )

    def delete_lineage(self, lineage_id: str) -> bool:
        """
        Delete a DataLineage record.
        
        Args:
            lineage_id: Unique identifier of the lineage to delete.
        
        Returns:
            True if deletion was successful, False if lineage not found.
        
        Raises:
            LineageError: If deletion fails.
        """
        try:
            query = "DELETE FROM data_lineage WHERE lineage_id = ?"
            rows_affected = self.db_connection.execute_update(query, (lineage_id,))
            
            if rows_affected > 0:
                logger.debug(f"Deleted lineage: {lineage_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete lineage: {e}", exc_info=True)
            raise LineageError(
                f"Failed to delete lineage: {e}",
                details={"lineage_id": lineage_id}
            )

    def delete_lineages_by_trace(self, trace_id: str) -> int:
        """
        Delete all lineage records for a specific trace.
        
        Args:
            trace_id: The trace identifier.
        
        Returns:
            Number of lineage records deleted.
        
        Raises:
            LineageError: If deletion fails.
        """
        try:
            query = "DELETE FROM data_lineage WHERE trace_id = ?"
            rows_affected = self.db_connection.execute_update(query, (trace_id,))
            
            logger.info(f"Deleted {rows_affected} lineages for trace: {trace_id}")
            return rows_affected
            
        except Exception as e:
            logger.error(f"Failed to delete lineages by trace: {e}", exc_info=True)
            raise LineageError(
                f"Failed to delete lineages by trace: {e}",
                details={"trace_id": trace_id}
            )

    def mark_stale_by_file(
        self,
        file_id: str,
        reason: str,
    ) -> int:
        """
        Mark all lineage records for a file as stale.
        
        Use this when a file has been modified and its lineage
        records may no longer be accurate.
        
        Args:
            file_id: The file identifier.
            reason: Explanation of why records are marked stale.
        
        Returns:
            Number of lineage records marked as stale.
        
        Raises:
            LineageError: If update fails.
        """
        try:
            query = """
                UPDATE data_lineage
                SET is_stale = 1, stale_reason = ?
                WHERE file_id = ? AND is_stale = 0
            """
            
            rows_affected = self.db_connection.execute_update(
                query, (reason, file_id)
            )
            
            if rows_affected > 0:
                logger.info(
                    f"Marked {rows_affected} lineages as stale for file: {file_id}"
                )
            
            return rows_affected
            
        except Exception as e:
            logger.error(f"Failed to mark lineages as stale: {e}", exc_info=True)
            raise LineageError(
                f"Failed to mark lineages as stale: {e}",
                details={"file_id": file_id}
            )

    def get_stale_lineages(self, limit: int = 100) -> List[DataLineage]:
        """
        Retrieve all stale lineage records.
        
        Args:
            limit: Maximum number of records to return.
        
        Returns:
            List of stale DataLineage objects.
        
        Raises:
            LineageError: If retrieval fails.
        """
        try:
            query = """
                SELECT 
                    dl.lineage_id, dl.answer_component, dl.file_id,
                    f.name as file_name, dl.sheet_name, dl.cell_range,
                    dl.source_value, dl.chunk_id, dl.embedding_id,
                    dl.retrieval_score, dl.indexed_at, dl.last_verified_at,
                    dl.is_stale, dl.stale_reason
                FROM data_lineage dl
                LEFT JOIN files f ON dl.file_id = f.file_id
                WHERE dl.is_stale = 1
                ORDER BY dl.indexed_at DESC
                LIMIT ?
            """
            
            results = self.db_connection.execute_query(query, (limit,))
            return [self._row_to_lineage(dict(row)) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get stale lineages: {e}", exc_info=True)
            raise LineageError(
                f"Failed to get stale lineages: {e}",
                details={}
            )

    def get_lineage_count(
        self,
        file_id: Optional[str] = None,
        is_stale: Optional[bool] = None,
    ) -> int:
        """
        Get the count of lineage records, optionally filtered.
        
        Args:
            file_id: Optional file ID to filter by.
            is_stale: Optional staleness filter.
        
        Returns:
            Number of lineage records matching the criteria.
        
        Raises:
            LineageError: If count fails.
        """
        try:
            clauses: List[str] = []
            params: List[Any] = []
            
            if file_id is not None:
                clauses.append("file_id = ?")
                params.append(file_id)
            
            if is_stale is not None:
                clauses.append("is_stale = ?")
                params.append(1 if is_stale else 0)
            
            where_clause = " AND ".join(clauses) if clauses else "1=1"
            query = f"SELECT COUNT(*) as count FROM data_lineage WHERE {where_clause}"
            
            results = self.db_connection.execute_query(query, tuple(params))
            return results[0]["count"] if results else 0
            
        except Exception as e:
            logger.error(f"Failed to get lineage count: {e}", exc_info=True)
            raise LineageError(
                f"Failed to get lineage count: {e}",
                details={"file_id": file_id, "is_stale": is_stale}
            )

    def batch_create_lineages(
        self,
        lineages: List[DataLineage],
        trace_id: str,
    ) -> int:
        """
        Create multiple lineage records in a batch.
        
        Args:
            lineages: List of DataLineage objects to create.
            trace_id: The trace ID these lineages belong to.
        
        Returns:
            Number of lineage records created.
        
        Raises:
            LineageError: If batch creation fails.
        """
        if not lineages:
            return 0
        
        try:
            query = """
                INSERT INTO data_lineage (
                    lineage_id, trace_id, answer_component, file_id,
                    sheet_name, cell_range, source_value, chunk_id,
                    embedding_id, retrieval_score, indexed_at,
                    last_verified_at, is_stale, stale_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params_list = [
                (
                    lineage.lineage_id,
                    trace_id,
                    lineage.answer_component,
                    lineage.file_id,
                    lineage.sheet_name,
                    lineage.cell_range,
                    lineage.source_value,
                    lineage.chunk_id,
                    lineage.embedding_id,
                    lineage.retrieval_score,
                    lineage.indexed_at,
                    lineage.last_verified_at,
                    lineage.is_stale,
                    lineage.stale_reason,
                )
                for lineage in lineages
            ]
            
            rows_affected = self.db_connection.execute_many(query, params_list)
            logger.info(f"Batch created {rows_affected} lineage records")
            return rows_affected
            
        except Exception as e:
            logger.error(f"Failed to batch create lineages: {e}", exc_info=True)
            raise LineageError(
                f"Failed to batch create lineages: {e}",
                details={"lineage_count": len(lineages)}
            )

    def _row_to_lineage(self, row: Dict[str, Any]) -> DataLineage:
        """Convert a database row to a DataLineage object."""
        return DataLineage(
            lineage_id=row["lineage_id"],
            answer_component=row["answer_component"],
            file_id=row["file_id"],
            file_name=row.get("file_name", ""),
            sheet_name=row["sheet_name"],
            cell_range=row["cell_range"],
            source_value=row.get("source_value", ""),
            chunk_id=row["chunk_id"],
            embedding_id=row.get("embedding_id", ""),
            retrieval_score=row.get("retrieval_score", 0.0),
            indexed_at=row.get("indexed_at", ""),
            last_verified_at=row.get("last_verified_at"),
            is_stale=bool(row.get("is_stale", False)),
            stale_reason=row.get("stale_reason"),
        )
