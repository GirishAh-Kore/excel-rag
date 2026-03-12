"""
Chunk Metadata Store

This module provides CRUD operations for chunk metadata storage and retrieval.
It supports filtering by file_id, sheet_name, extraction_strategy, and content_type,
with connection pooling for efficient database access.

Key Features:
- Create, read, update, delete chunk metadata
- Filter chunks by multiple criteria (AND logic)
- Pagination support for large result sets
- Connection pooling via DatabaseConnection

Requirements: 1.1, 1.3, 2.2
"""

import json
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.database.connection import DatabaseConnection
from src.exceptions import ChunkViewerError
from src.models.chunk_visibility import (
    ChunkDetails,
    ChunkFilters,
    ExtractionMetadata,
    PaginatedChunkResponse,
)

logger = logging.getLogger(__name__)


class ChunkMetadataStore:
    """
    Manages CRUD operations for chunk metadata in SQLite database.
    
    Provides efficient storage and retrieval of chunk metadata with support
    for filtering by file_id, sheet_name, extraction_strategy, and content_type.
    Uses connection pooling via the injected DatabaseConnection.
    
    Attributes:
        db_connection: Injected database connection with connection pooling.
    
    Requirements: 1.1, 1.3, 2.2
    """
    
    # Default pagination settings
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize the chunk metadata store.
        
        Args:
            db_connection: Database connection instance with connection pooling.
        
        Raises:
            ChunkViewerError: If db_connection is None.
        """
        if db_connection is None:
            raise ChunkViewerError(
                "Database connection is required",
                details={"parameter": "db_connection"}
            )
        self.db_connection = db_connection
        logger.info("ChunkMetadataStore initialized")
    
    def create_chunk(self, chunk: ChunkDetails) -> str:
        """
        Create a new chunk metadata record.
        
        Args:
            chunk: ChunkDetails object containing chunk metadata.
        
        Returns:
            The chunk_id of the created chunk.
        
        Raises:
            ChunkViewerError: If chunk creation fails.
        """
        try:
            query = """
                INSERT INTO chunk_versions (
                    chunk_id, file_id, version_number, chunk_text, raw_source_data,
                    start_row, end_row, extraction_strategy, indexed_at, change_summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id, version_number) DO UPDATE SET
                    chunk_text = excluded.chunk_text,
                    raw_source_data = excluded.raw_source_data,
                    start_row = excluded.start_row,
                    end_row = excluded.end_row,
                    extraction_strategy = excluded.extraction_strategy,
                    indexed_at = excluded.indexed_at
            """
            
            params = (
                chunk.chunk_id,
                chunk.file_id,
                1,  # Initial version
                chunk.chunk_text,
                chunk.raw_source_data,
                chunk.start_row,
                chunk.end_row,
                chunk.extraction_strategy,
                datetime.now().isoformat(),
                None,  # No change summary for initial version
            )
            
            self.db_connection.execute_insert(query, params)
            logger.debug(f"Created chunk metadata: {chunk.chunk_id}")
            return chunk.chunk_id
            
        except Exception as e:
            logger.error(f"Failed to create chunk metadata: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to create chunk metadata: {e}",
                details={"chunk_id": chunk.chunk_id, "file_id": chunk.file_id}
            )
    
    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a chunk by its ID.
        
        Args:
            chunk_id: Unique identifier of the chunk.
        
        Returns:
            Dictionary containing chunk metadata, or None if not found.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        """
        try:
            query = """
                SELECT 
                    cv.chunk_id,
                    cv.file_id,
                    f.name as file_name,
                    cv.version_number,
                    cv.chunk_text,
                    cv.raw_source_data,
                    cv.start_row,
                    cv.end_row,
                    cv.extraction_strategy,
                    cv.indexed_at,
                    cv.change_summary
                FROM chunk_versions cv
                LEFT JOIN files f ON cv.file_id = f.file_id
                WHERE cv.chunk_id = ?
                ORDER BY cv.version_number DESC
                LIMIT 1
            """
            
            results = self.db_connection.execute_query(query, (chunk_id,))
            
            if not results:
                return None
            
            row = results[0]
            return dict(row)
            
        except Exception as e:
            logger.error(f"Failed to get chunk metadata: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get chunk metadata: {e}",
                details={"chunk_id": chunk_id}
            )
    
    def update_chunk(
        self,
        chunk_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update an existing chunk's metadata.
        
        Args:
            chunk_id: Unique identifier of the chunk to update.
            updates: Dictionary of fields to update.
        
        Returns:
            True if update was successful, False if chunk not found.
        
        Raises:
            ChunkViewerError: If update fails.
        """
        if not updates:
            return True
        
        # Allowed fields for update
        allowed_fields = {
            "chunk_text", "raw_source_data", "start_row", "end_row",
            "extraction_strategy", "change_summary"
        }
        
        # Filter to only allowed fields
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not filtered_updates:
            logger.warning(f"No valid fields to update for chunk {chunk_id}")
            return True
        
        try:
            # Build dynamic UPDATE query
            set_clauses = [f"{field} = ?" for field in filtered_updates.keys()]
            set_clause = ", ".join(set_clauses)
            
            query = f"""
                UPDATE chunk_versions
                SET {set_clause}, indexed_at = ?
                WHERE chunk_id = ? AND version_number = (
                    SELECT MAX(version_number) FROM chunk_versions WHERE chunk_id = ?
                )
            """
            
            params = tuple(filtered_updates.values()) + (
                datetime.now().isoformat(),
                chunk_id,
                chunk_id,
            )
            
            rows_affected = self.db_connection.execute_update(query, params)
            
            if rows_affected > 0:
                logger.debug(f"Updated chunk metadata: {chunk_id}")
                return True
            else:
                logger.warning(f"Chunk not found for update: {chunk_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update chunk metadata: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to update chunk metadata: {e}",
                details={"chunk_id": chunk_id, "updates": list(filtered_updates.keys())}
            )
    
    def delete_chunk(self, chunk_id: str) -> bool:
        """
        Delete a chunk and all its versions.
        
        Args:
            chunk_id: Unique identifier of the chunk to delete.
        
        Returns:
            True if deletion was successful, False if chunk not found.
        
        Raises:
            ChunkViewerError: If deletion fails.
        """
        try:
            query = "DELETE FROM chunk_versions WHERE chunk_id = ?"
            rows_affected = self.db_connection.execute_update(query, (chunk_id,))
            
            if rows_affected > 0:
                logger.debug(f"Deleted chunk metadata: {chunk_id}")
                return True
            else:
                logger.warning(f"Chunk not found for deletion: {chunk_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete chunk metadata: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to delete chunk metadata: {e}",
                details={"chunk_id": chunk_id}
            )
    
    def delete_chunks_by_file(self, file_id: str) -> int:
        """
        Delete all chunks for a specific file.
        
        Args:
            file_id: File ID whose chunks should be deleted.
        
        Returns:
            Number of chunks deleted.
        
        Raises:
            ChunkViewerError: If deletion fails.
        """
        try:
            query = "DELETE FROM chunk_versions WHERE file_id = ?"
            rows_affected = self.db_connection.execute_update(query, (file_id,))
            
            logger.info(f"Deleted {rows_affected} chunks for file: {file_id}")
            return rows_affected
            
        except Exception as e:
            logger.error(f"Failed to delete chunks by file: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to delete chunks by file: {e}",
                details={"file_id": file_id}
            )
    
    def get_chunks_for_file(
        self,
        file_id: str,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE
    ) -> PaginatedChunkResponse:
        """
        Get all chunks for a specific file with pagination.
        
        Args:
            file_id: File ID to get chunks for.
            page: Page number (1-indexed).
            page_size: Number of items per page (max 100).
        
        Returns:
            PaginatedChunkResponse containing chunks and pagination metadata.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        
        Requirements: 1.1
        """
        filters = ChunkFilters(file_id=file_id)
        return self.get_chunks_with_filters(filters, page, page_size)
    
    def get_chunks_for_sheet(
        self,
        file_id: str,
        sheet_name: str,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE
    ) -> PaginatedChunkResponse:
        """
        Get chunks for a specific sheet within a file.
        
        Note: Sheet name filtering requires joining with vector store metadata
        or storing sheet_name in chunk_versions table. This implementation
        uses a workaround by searching chunk_text for sheet references.
        
        Args:
            file_id: File ID containing the sheet.
            sheet_name: Name of the sheet to filter by.
            page: Page number (1-indexed).
            page_size: Number of items per page (max 100).
        
        Returns:
            PaginatedChunkResponse containing chunks and pagination metadata.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        
        Requirements: 1.3
        """
        filters = ChunkFilters(file_id=file_id, sheet_name=sheet_name)
        return self.get_chunks_with_filters(filters, page, page_size)
    
    def get_chunks_with_filters(
        self,
        filters: Optional[ChunkFilters] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE
    ) -> PaginatedChunkResponse:
        """
        Get chunks with optional filtering and pagination.
        
        Filters are combined using AND logic. Supports filtering by:
        - file_id: Filter by file
        - sheet_name: Filter by sheet (requires metadata join)
        - extraction_strategy: Filter by extraction method
        - content_type: Filter by content type
        
        Args:
            filters: Optional ChunkFilters object with filter criteria.
            page: Page number (1-indexed).
            page_size: Number of items per page (max 100).
        
        Returns:
            PaginatedChunkResponse containing chunks and pagination metadata.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        
        Requirements: 2.2
        """
        # Validate pagination parameters
        page = max(1, page)
        page_size = min(max(1, page_size), self.MAX_PAGE_SIZE)
        offset = (page - 1) * page_size
        
        try:
            # Build WHERE clause and parameters
            where_clauses, params = self._build_filter_clauses(filters)
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # Get total count
            count_query = f"""
                SELECT COUNT(DISTINCT cv.chunk_id) as total
                FROM chunk_versions cv
                LEFT JOIN files f ON cv.file_id = f.file_id
                LEFT JOIN extraction_metadata em ON cv.file_id = em.file_id
                WHERE {where_clause}
            """
            count_result = self.db_connection.execute_query(count_query, params)
            total_count = count_result[0]["total"] if count_result else 0
            
            # Get paginated chunks (latest version of each)
            data_query = f"""
                SELECT 
                    cv.chunk_id,
                    cv.file_id,
                    f.name as file_name,
                    cv.version_number,
                    cv.chunk_text,
                    cv.raw_source_data,
                    cv.start_row,
                    cv.end_row,
                    cv.extraction_strategy,
                    cv.indexed_at,
                    cv.change_summary,
                    em.quality_score
                FROM chunk_versions cv
                LEFT JOIN files f ON cv.file_id = f.file_id
                LEFT JOIN extraction_metadata em ON cv.file_id = em.file_id
                WHERE {where_clause}
                AND cv.version_number = (
                    SELECT MAX(cv2.version_number) 
                    FROM chunk_versions cv2 
                    WHERE cv2.chunk_id = cv.chunk_id
                )
                ORDER BY cv.file_id, cv.chunk_id
                LIMIT ? OFFSET ?
            """
            
            data_params = params + (page_size, offset)
            results = self.db_connection.execute_query(data_query, data_params)
            
            # Convert to list of dicts
            chunks = [dict(row) for row in results]
            
            # Calculate has_more
            has_more = (offset + len(chunks)) < total_count
            
            return PaginatedChunkResponse(
                chunks=chunks,
                total_count=total_count,
                page=page,
                page_size=page_size,
                has_more=has_more
            )
            
        except Exception as e:
            logger.error(f"Failed to get chunks with filters: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get chunks with filters: {e}",
                details={"filters": filters.to_dict() if filters else None}
            )
    
    def _build_filter_clauses(
        self,
        filters: Optional[ChunkFilters]
    ) -> Tuple[List[str], Tuple[Any, ...]]:
        """
        Build SQL WHERE clauses from ChunkFilters.
        
        Args:
            filters: Optional ChunkFilters object.
        
        Returns:
            Tuple of (list of WHERE clauses, tuple of parameters).
        """
        clauses: List[str] = []
        params: List[Any] = []
        
        if filters is None or filters.is_empty():
            return clauses, tuple(params)
        
        if filters.file_id is not None:
            clauses.append("cv.file_id = ?")
            params.append(filters.file_id)
        
        if filters.extraction_strategy is not None:
            clauses.append("cv.extraction_strategy = ?")
            params.append(filters.extraction_strategy)
        
        if filters.sheet_name is not None:
            # Sheet name is typically stored in vector store metadata
            # For now, we search in chunk_text as a workaround
            clauses.append("cv.chunk_text LIKE ?")
            params.append(f"%{filters.sheet_name}%")
        
        if filters.content_type is not None:
            # Content type is stored in vector store metadata
            # For now, we search in chunk_text as a workaround
            clauses.append("cv.chunk_text LIKE ?")
            params.append(f"%{filters.content_type}%")
        
        if filters.min_quality_score is not None:
            clauses.append("em.quality_score >= ?")
            params.append(filters.min_quality_score)
        
        return clauses, tuple(params)
    
    def get_extraction_metadata(self, file_id: str) -> Optional[ExtractionMetadata]:
        """
        Get extraction metadata for a file.
        
        Args:
            file_id: File ID to get extraction metadata for.
        
        Returns:
            ExtractionMetadata object or None if not found.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        
        Requirements: 1.3
        """
        try:
            query = """
                SELECT 
                    file_id,
                    strategy_used,
                    strategy_selected_reason,
                    complexity_score,
                    quality_score,
                    has_headers,
                    has_data,
                    data_completeness,
                    structure_clarity,
                    extraction_errors,
                    extraction_warnings,
                    fallback_used,
                    fallback_reason,
                    extraction_duration_ms,
                    extracted_at
                FROM extraction_metadata
                WHERE file_id = ?
            """
            
            results = self.db_connection.execute_query(query, (file_id,))
            
            if not results:
                return None
            
            row = dict(results[0])
            
            # Parse JSON fields
            extraction_errors = json.loads(row.get("extraction_errors") or "[]")
            extraction_warnings = json.loads(row.get("extraction_warnings") or "[]")
            
            return ExtractionMetadata(
                file_id=row["file_id"],
                strategy_used=row["strategy_used"],
                strategy_selected_reason=row.get("strategy_selected_reason"),
                complexity_score=row.get("complexity_score"),
                quality_score=row["quality_score"],
                has_headers=bool(row.get("has_headers")),
                has_data=bool(row.get("has_data")),
                data_completeness=row.get("data_completeness", 0.0),
                structure_clarity=row.get("structure_clarity", 0.0),
                extraction_errors=extraction_errors,
                extraction_warnings=extraction_warnings,
                fallback_used=bool(row.get("fallback_used")),
                fallback_reason=row.get("fallback_reason"),
                extraction_duration_ms=row.get("extraction_duration_ms", 0),
                extracted_at=row.get("extracted_at", ""),
            )
            
        except Exception as e:
            logger.error(f"Failed to get extraction metadata: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get extraction metadata: {e}",
                details={"file_id": file_id}
            )
    
    def save_extraction_metadata(self, metadata: ExtractionMetadata) -> bool:
        """
        Save or update extraction metadata for a file.
        
        Args:
            metadata: ExtractionMetadata object to save.
        
        Returns:
            True if save was successful.
        
        Raises:
            ChunkViewerError: If save fails.
        """
        try:
            query = """
                INSERT INTO extraction_metadata (
                    file_id, strategy_used, strategy_selected_reason, complexity_score,
                    quality_score, has_headers, has_data, data_completeness,
                    structure_clarity, extraction_errors, extraction_warnings,
                    fallback_used, fallback_reason, extraction_duration_ms, extracted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    strategy_used = excluded.strategy_used,
                    strategy_selected_reason = excluded.strategy_selected_reason,
                    complexity_score = excluded.complexity_score,
                    quality_score = excluded.quality_score,
                    has_headers = excluded.has_headers,
                    has_data = excluded.has_data,
                    data_completeness = excluded.data_completeness,
                    structure_clarity = excluded.structure_clarity,
                    extraction_errors = excluded.extraction_errors,
                    extraction_warnings = excluded.extraction_warnings,
                    fallback_used = excluded.fallback_used,
                    fallback_reason = excluded.fallback_reason,
                    extraction_duration_ms = excluded.extraction_duration_ms,
                    extracted_at = excluded.extracted_at
            """
            
            params = (
                metadata.file_id,
                metadata.strategy_used,
                metadata.strategy_selected_reason,
                metadata.complexity_score,
                metadata.quality_score,
                metadata.has_headers,
                metadata.has_data,
                metadata.data_completeness,
                metadata.structure_clarity,
                json.dumps(metadata.extraction_errors),
                json.dumps(metadata.extraction_warnings),
                metadata.fallback_used,
                metadata.fallback_reason,
                metadata.extraction_duration_ms,
                metadata.extracted_at or datetime.now().isoformat(),
            )
            
            self.db_connection.execute_insert(query, params)
            logger.debug(f"Saved extraction metadata for file: {metadata.file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save extraction metadata: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to save extraction metadata: {e}",
                details={"file_id": metadata.file_id}
            )
    
    def get_chunk_count_by_file(self, file_id: str) -> int:
        """
        Get the count of chunks for a specific file.
        
        Args:
            file_id: File ID to count chunks for.
        
        Returns:
            Number of chunks for the file.
        
        Raises:
            ChunkViewerError: If count fails.
        """
        try:
            query = """
                SELECT COUNT(DISTINCT chunk_id) as count
                FROM chunk_versions
                WHERE file_id = ?
            """
            
            results = self.db_connection.execute_query(query, (file_id,))
            return results[0]["count"] if results else 0
            
        except Exception as e:
            logger.error(f"Failed to get chunk count: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get chunk count: {e}",
                details={"file_id": file_id}
            )
    
    def get_chunk_statistics(self) -> Dict[str, Any]:
        """
        Get overall statistics about stored chunks.
        
        Returns:
            Dictionary containing chunk statistics.
        
        Raises:
            ChunkViewerError: If statistics retrieval fails.
        """
        try:
            stats_query = """
                SELECT 
                    COUNT(DISTINCT chunk_id) as total_chunks,
                    COUNT(DISTINCT file_id) as total_files,
                    COUNT(*) as total_versions,
                    AVG(end_row - start_row) as avg_chunk_rows
                FROM chunk_versions
            """
            
            results = self.db_connection.execute_query(stats_query)
            
            if not results:
                return {
                    "total_chunks": 0,
                    "total_files": 0,
                    "total_versions": 0,
                    "avg_chunk_rows": 0,
                    "chunks_by_strategy": {},
                }
            
            row = dict(results[0])
            
            # Get chunks by extraction strategy
            strategy_query = """
                SELECT extraction_strategy, COUNT(DISTINCT chunk_id) as count
                FROM chunk_versions
                GROUP BY extraction_strategy
            """
            strategy_results = self.db_connection.execute_query(strategy_query)
            chunks_by_strategy = {
                r["extraction_strategy"]: r["count"] 
                for r in strategy_results
            }
            
            return {
                "total_chunks": row.get("total_chunks", 0),
                "total_files": row.get("total_files", 0),
                "total_versions": row.get("total_versions", 0),
                "avg_chunk_rows": round(row.get("avg_chunk_rows") or 0, 2),
                "chunks_by_strategy": chunks_by_strategy,
            }
            
        except Exception as e:
            logger.error(f"Failed to get chunk statistics: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get chunk statistics: {e}",
                details={}
            )
    
    def batch_create_chunks(self, chunks: List[ChunkDetails]) -> int:
        """
        Create multiple chunk metadata records in a batch.
        
        Args:
            chunks: List of ChunkDetails objects to create.
        
        Returns:
            Number of chunks created.
        
        Raises:
            ChunkViewerError: If batch creation fails.
        """
        if not chunks:
            return 0
        
        try:
            query = """
                INSERT INTO chunk_versions (
                    chunk_id, file_id, version_number, chunk_text, raw_source_data,
                    start_row, end_row, extraction_strategy, indexed_at, change_summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id, version_number) DO UPDATE SET
                    chunk_text = excluded.chunk_text,
                    raw_source_data = excluded.raw_source_data,
                    start_row = excluded.start_row,
                    end_row = excluded.end_row,
                    extraction_strategy = excluded.extraction_strategy,
                    indexed_at = excluded.indexed_at
            """
            
            now = datetime.now().isoformat()
            params_list = [
                (
                    chunk.chunk_id,
                    chunk.file_id,
                    1,  # Initial version
                    chunk.chunk_text,
                    chunk.raw_source_data,
                    chunk.start_row,
                    chunk.end_row,
                    chunk.extraction_strategy,
                    now,
                    None,
                )
                for chunk in chunks
            ]
            
            rows_affected = self.db_connection.execute_many(query, params_list)
            logger.info(f"Batch created {rows_affected} chunk metadata records")
            return rows_affected
            
        except Exception as e:
            logger.error(f"Failed to batch create chunks: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to batch create chunks: {e}",
                details={"chunk_count": len(chunks)}
            )
