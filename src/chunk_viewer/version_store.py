"""
Chunk Version Store

This module provides version management for chunks during re-indexing.
It supports version creation, history retrieval, diff comparison, and rollback.

Key Features:
- Create new versions when files are re-indexed
- Retrieve version history for any chunk
- Compare content between versions with diff generation
- Rollback to previous versions

Requirements: 21.1, 21.2, 21.3, 21.4, 21.5
"""

import difflib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.database.connection import DatabaseConnection
from src.exceptions import ChunkViewerError
from src.models.chunk_visibility import ChunkVersion

logger = logging.getLogger(__name__)


@dataclass
class VersionDiff:
    """
    Represents the difference between two chunk versions.
    
    Attributes:
        chunk_id: ID of the chunk being compared.
        from_version: Source version number.
        to_version: Target version number.
        added_lines: Lines added in the target version.
        removed_lines: Lines removed from the source version.
        unchanged_lines: Lines that remain the same.
        diff_text: Unified diff format text.
        similarity_ratio: Ratio of similarity between versions (0.0 to 1.0).
    """
    chunk_id: str
    from_version: int
    to_version: int
    added_lines: int
    removed_lines: int
    unchanged_lines: int
    diff_text: str
    similarity_ratio: float


class ChunkVersionStore:
    """
    Manages chunk version storage and retrieval.
    
    Provides functionality for tracking chunk changes across re-indexing events,
    comparing versions, and rolling back to previous versions.
    
    Attributes:
        db_connection: Injected database connection with connection pooling.
    
    Requirements: 21.1, 21.2, 21.3, 21.4, 21.5
    """
    
    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize the chunk version store.
        
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
        logger.info("ChunkVersionStore initialized")
    
    def create_version(
        self,
        chunk_id: str,
        file_id: str,
        chunk_text: str,
        extraction_strategy: str,
        raw_source_data: Optional[str] = None,
        start_row: Optional[int] = None,
        end_row: Optional[int] = None,
        change_summary: Optional[str] = None,
    ) -> ChunkVersion:
        """
        Create a new version for a chunk during re-indexing.
        
        If the chunk already exists, creates a new version with incremented
        version number. If it's a new chunk, creates version 1.
        
        Args:
            chunk_id: Unique identifier for the chunk.
            file_id: ID of the file this chunk belongs to.
            chunk_text: The processed chunk text content.
            extraction_strategy: Strategy used for extraction.
            raw_source_data: Optional raw source data before processing.
            start_row: Optional starting row number.
            end_row: Optional ending row number.
            change_summary: Optional summary of changes from previous version.
        
        Returns:
            ChunkVersion object representing the created version.
        
        Raises:
            ChunkViewerError: If version creation fails.
        
        Requirements: 21.1
        """
        try:
            # Get the next version number
            next_version = self._get_next_version_number(chunk_id)
            
            # Auto-generate change summary if not provided and this isn't version 1
            if change_summary is None and next_version > 1:
                previous_version = self.get_version(chunk_id, next_version - 1)
                if previous_version:
                    change_summary = self._generate_change_summary(
                        previous_version.chunk_text,
                        chunk_text
                    )
            
            version_id = str(uuid.uuid4())
            indexed_at = datetime.now()
            
            query = """
                INSERT INTO chunk_versions (
                    chunk_id, file_id, version_number, chunk_text, raw_source_data,
                    start_row, end_row, extraction_strategy, indexed_at, change_summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                chunk_id,
                file_id,
                next_version,
                chunk_text,
                raw_source_data,
                start_row,
                end_row,
                extraction_strategy,
                indexed_at.isoformat(),
                change_summary,
            )
            
            self.db_connection.execute_insert(query, params)
            
            logger.debug(
                f"Created version {next_version} for chunk {chunk_id}"
            )
            
            return ChunkVersion(
                version_id=version_id,
                chunk_id=chunk_id,
                version_number=next_version,
                chunk_text=chunk_text,
                extraction_strategy=extraction_strategy,
                indexed_at=indexed_at,
                change_summary=change_summary,
            )
            
        except Exception as e:
            logger.error(f"Failed to create chunk version: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to create chunk version: {e}",
                details={"chunk_id": chunk_id, "file_id": file_id}
            )
    
    def get_version(
        self,
        chunk_id: str,
        version_number: int
    ) -> Optional[ChunkVersion]:
        """
        Retrieve a specific version of a chunk.
        
        Args:
            chunk_id: Unique identifier of the chunk.
            version_number: Version number to retrieve.
        
        Returns:
            ChunkVersion object or None if not found.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        """
        try:
            query = """
                SELECT 
                    chunk_id,
                    version_number,
                    chunk_text,
                    extraction_strategy,
                    indexed_at,
                    change_summary
                FROM chunk_versions
                WHERE chunk_id = ? AND version_number = ?
            """
            
            results = self.db_connection.execute_query(
                query, (chunk_id, version_number)
            )
            
            if not results:
                return None
            
            row = dict(results[0])
            
            # Parse indexed_at timestamp
            indexed_at_str = row.get("indexed_at", "")
            if indexed_at_str:
                indexed_at = datetime.fromisoformat(indexed_at_str)
            else:
                indexed_at = datetime.now()
            
            return ChunkVersion(
                version_id=f"{chunk_id}_v{version_number}",
                chunk_id=row["chunk_id"],
                version_number=row["version_number"],
                chunk_text=row["chunk_text"],
                extraction_strategy=row["extraction_strategy"],
                indexed_at=indexed_at,
                change_summary=row.get("change_summary"),
            )
            
        except Exception as e:
            logger.error(f"Failed to get chunk version: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get chunk version: {e}",
                details={"chunk_id": chunk_id, "version_number": version_number}
            )
    
    def get_latest_version(self, chunk_id: str) -> Optional[ChunkVersion]:
        """
        Retrieve the latest version of a chunk.
        
        Args:
            chunk_id: Unique identifier of the chunk.
        
        Returns:
            ChunkVersion object or None if chunk has no versions.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        """
        try:
            query = """
                SELECT 
                    chunk_id,
                    version_number,
                    chunk_text,
                    extraction_strategy,
                    indexed_at,
                    change_summary
                FROM chunk_versions
                WHERE chunk_id = ?
                ORDER BY version_number DESC
                LIMIT 1
            """
            
            results = self.db_connection.execute_query(query, (chunk_id,))
            
            if not results:
                return None
            
            row = dict(results[0])
            
            indexed_at_str = row.get("indexed_at", "")
            if indexed_at_str:
                indexed_at = datetime.fromisoformat(indexed_at_str)
            else:
                indexed_at = datetime.now()
            
            return ChunkVersion(
                version_id=f"{chunk_id}_v{row['version_number']}",
                chunk_id=row["chunk_id"],
                version_number=row["version_number"],
                chunk_text=row["chunk_text"],
                extraction_strategy=row["extraction_strategy"],
                indexed_at=indexed_at,
                change_summary=row.get("change_summary"),
            )
            
        except Exception as e:
            logger.error(f"Failed to get latest chunk version: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get latest chunk version: {e}",
                details={"chunk_id": chunk_id}
            )

    
    def get_version_history(
        self,
        chunk_id: str,
        limit: Optional[int] = None
    ) -> List[ChunkVersion]:
        """
        Retrieve version history for a chunk.
        
        Returns versions in descending order (newest first).
        
        Args:
            chunk_id: Unique identifier of the chunk.
            limit: Optional maximum number of versions to return.
        
        Returns:
            List of ChunkVersion objects ordered by version_number descending.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        
        Requirements: 21.2
        """
        try:
            query = """
                SELECT 
                    chunk_id,
                    version_number,
                    chunk_text,
                    extraction_strategy,
                    indexed_at,
                    change_summary
                FROM chunk_versions
                WHERE chunk_id = ?
                ORDER BY version_number DESC
            """
            
            if limit is not None and limit > 0:
                query += f" LIMIT {limit}"
            
            results = self.db_connection.execute_query(query, (chunk_id,))
            
            versions: List[ChunkVersion] = []
            for row in results:
                row_dict = dict(row)
                
                indexed_at_str = row_dict.get("indexed_at", "")
                if indexed_at_str:
                    indexed_at = datetime.fromisoformat(indexed_at_str)
                else:
                    indexed_at = datetime.now()
                
                versions.append(ChunkVersion(
                    version_id=f"{chunk_id}_v{row_dict['version_number']}",
                    chunk_id=row_dict["chunk_id"],
                    version_number=row_dict["version_number"],
                    chunk_text=row_dict["chunk_text"],
                    extraction_strategy=row_dict["extraction_strategy"],
                    indexed_at=indexed_at,
                    change_summary=row_dict.get("change_summary"),
                ))
            
            return versions
            
        except Exception as e:
            logger.error(f"Failed to get version history: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get version history: {e}",
                details={"chunk_id": chunk_id}
            )
    
    def get_versions_for_file(
        self,
        file_id: str,
        version_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all chunk versions for a file.
        
        Args:
            file_id: ID of the file to get versions for.
            version_number: Optional specific version number to filter by.
        
        Returns:
            List of dictionaries containing version information.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        
        Requirements: 21.2
        """
        try:
            if version_number is not None:
                query = """
                    SELECT 
                        chunk_id,
                        file_id,
                        version_number,
                        chunk_text,
                        raw_source_data,
                        start_row,
                        end_row,
                        extraction_strategy,
                        indexed_at,
                        change_summary
                    FROM chunk_versions
                    WHERE file_id = ? AND version_number = ?
                    ORDER BY chunk_id
                """
                params: Tuple[Any, ...] = (file_id, version_number)
            else:
                query = """
                    SELECT 
                        chunk_id,
                        file_id,
                        version_number,
                        chunk_text,
                        raw_source_data,
                        start_row,
                        end_row,
                        extraction_strategy,
                        indexed_at,
                        change_summary
                    FROM chunk_versions
                    WHERE file_id = ?
                    ORDER BY chunk_id, version_number DESC
                """
                params = (file_id,)
            
            results = self.db_connection.execute_query(query, params)
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get versions for file: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get versions for file: {e}",
                details={"file_id": file_id}
            )
    
    def compare_versions(
        self,
        chunk_id: str,
        from_version: int,
        to_version: int
    ) -> VersionDiff:
        """
        Compare two versions of a chunk and generate a diff.
        
        Args:
            chunk_id: Unique identifier of the chunk.
            from_version: Source version number.
            to_version: Target version number.
        
        Returns:
            VersionDiff object containing comparison details.
        
        Raises:
            ChunkViewerError: If either version is not found or comparison fails.
        
        Requirements: 21.3
        """
        try:
            # Get both versions
            from_ver = self.get_version(chunk_id, from_version)
            to_ver = self.get_version(chunk_id, to_version)
            
            if from_ver is None:
                raise ChunkViewerError(
                    f"Version {from_version} not found for chunk {chunk_id}",
                    details={"chunk_id": chunk_id, "version": from_version}
                )
            
            if to_ver is None:
                raise ChunkViewerError(
                    f"Version {to_version} not found for chunk {chunk_id}",
                    details={"chunk_id": chunk_id, "version": to_version}
                )
            
            # Generate diff
            from_lines = from_ver.chunk_text.splitlines(keepends=True)
            to_lines = to_ver.chunk_text.splitlines(keepends=True)
            
            # Calculate unified diff
            diff = list(difflib.unified_diff(
                from_lines,
                to_lines,
                fromfile=f"v{from_version}",
                tofile=f"v{to_version}",
                lineterm=""
            ))
            diff_text = "".join(diff)
            
            # Count changes
            added_lines = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
            removed_lines = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
            
            # Calculate similarity ratio
            matcher = difflib.SequenceMatcher(
                None,
                from_ver.chunk_text,
                to_ver.chunk_text
            )
            similarity_ratio = matcher.ratio()
            
            # Calculate unchanged lines
            unchanged_lines = len(from_lines) - removed_lines
            
            return VersionDiff(
                chunk_id=chunk_id,
                from_version=from_version,
                to_version=to_version,
                added_lines=added_lines,
                removed_lines=removed_lines,
                unchanged_lines=max(0, unchanged_lines),
                diff_text=diff_text,
                similarity_ratio=round(similarity_ratio, 4),
            )
            
        except ChunkViewerError:
            raise
        except Exception as e:
            logger.error(f"Failed to compare versions: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to compare versions: {e}",
                details={
                    "chunk_id": chunk_id,
                    "from_version": from_version,
                    "to_version": to_version
                }
            )
    
    def rollback_to_version(
        self,
        chunk_id: str,
        target_version: int
    ) -> ChunkVersion:
        """
        Rollback a chunk to a previous version.
        
        Creates a new version with the content from the target version,
        preserving the version history.
        
        Args:
            chunk_id: Unique identifier of the chunk.
            target_version: Version number to rollback to.
        
        Returns:
            ChunkVersion object representing the new version created from rollback.
        
        Raises:
            ChunkViewerError: If target version not found or rollback fails.
        
        Requirements: 21.4, 21.5
        """
        try:
            # Get the target version
            target_ver = self.get_version(chunk_id, target_version)
            
            if target_ver is None:
                raise ChunkViewerError(
                    f"Target version {target_version} not found for chunk {chunk_id}",
                    details={"chunk_id": chunk_id, "target_version": target_version}
                )
            
            # Get the file_id from the target version
            query = """
                SELECT file_id, raw_source_data, start_row, end_row
                FROM chunk_versions
                WHERE chunk_id = ? AND version_number = ?
            """
            results = self.db_connection.execute_query(
                query, (chunk_id, target_version)
            )
            
            if not results:
                raise ChunkViewerError(
                    f"Could not retrieve full version data for rollback",
                    details={"chunk_id": chunk_id, "target_version": target_version}
                )
            
            row = dict(results[0])
            
            # Create a new version with the rolled-back content
            change_summary = f"Rolled back to version {target_version}"
            
            new_version = self.create_version(
                chunk_id=chunk_id,
                file_id=row["file_id"],
                chunk_text=target_ver.chunk_text,
                extraction_strategy=target_ver.extraction_strategy,
                raw_source_data=row.get("raw_source_data"),
                start_row=row.get("start_row"),
                end_row=row.get("end_row"),
                change_summary=change_summary,
            )
            
            logger.info(
                f"Rolled back chunk {chunk_id} to version {target_version}, "
                f"created version {new_version.version_number}"
            )
            
            return new_version
            
        except ChunkViewerError:
            raise
        except Exception as e:
            logger.error(f"Failed to rollback to version: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to rollback to version: {e}",
                details={"chunk_id": chunk_id, "target_version": target_version}
            )
    
    def delete_version(
        self,
        chunk_id: str,
        version_number: int
    ) -> bool:
        """
        Delete a specific version of a chunk.
        
        Note: Cannot delete the only remaining version of a chunk.
        
        Args:
            chunk_id: Unique identifier of the chunk.
            version_number: Version number to delete.
        
        Returns:
            True if deletion was successful, False if version not found.
        
        Raises:
            ChunkViewerError: If deletion fails or would leave chunk with no versions.
        """
        try:
            # Check if this is the only version
            count_query = """
                SELECT COUNT(*) as count
                FROM chunk_versions
                WHERE chunk_id = ?
            """
            count_result = self.db_connection.execute_query(count_query, (chunk_id,))
            version_count = count_result[0]["count"] if count_result else 0
            
            if version_count <= 1:
                raise ChunkViewerError(
                    "Cannot delete the only remaining version of a chunk",
                    details={"chunk_id": chunk_id, "version_number": version_number}
                )
            
            # Delete the version
            delete_query = """
                DELETE FROM chunk_versions
                WHERE chunk_id = ? AND version_number = ?
            """
            rows_affected = self.db_connection.execute_update(
                delete_query, (chunk_id, version_number)
            )
            
            if rows_affected > 0:
                logger.debug(
                    f"Deleted version {version_number} for chunk {chunk_id}"
                )
                return True
            else:
                logger.warning(
                    f"Version {version_number} not found for chunk {chunk_id}"
                )
                return False
                
        except ChunkViewerError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete version: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to delete version: {e}",
                details={"chunk_id": chunk_id, "version_number": version_number}
            )
    
    def delete_all_versions(self, chunk_id: str) -> int:
        """
        Delete all versions of a chunk.
        
        Args:
            chunk_id: Unique identifier of the chunk.
        
        Returns:
            Number of versions deleted.
        
        Raises:
            ChunkViewerError: If deletion fails.
        """
        try:
            query = "DELETE FROM chunk_versions WHERE chunk_id = ?"
            rows_affected = self.db_connection.execute_update(query, (chunk_id,))
            
            logger.info(f"Deleted {rows_affected} versions for chunk {chunk_id}")
            return rows_affected
            
        except Exception as e:
            logger.error(f"Failed to delete all versions: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to delete all versions: {e}",
                details={"chunk_id": chunk_id}
            )
    
    def get_version_count(self, chunk_id: str) -> int:
        """
        Get the number of versions for a chunk.
        
        Args:
            chunk_id: Unique identifier of the chunk.
        
        Returns:
            Number of versions for the chunk.
        
        Raises:
            ChunkViewerError: If count fails.
        """
        try:
            query = """
                SELECT COUNT(*) as count
                FROM chunk_versions
                WHERE chunk_id = ?
            """
            results = self.db_connection.execute_query(query, (chunk_id,))
            return results[0]["count"] if results else 0
            
        except Exception as e:
            logger.error(f"Failed to get version count: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get version count: {e}",
                details={"chunk_id": chunk_id}
            )
    
    def _get_next_version_number(self, chunk_id: str) -> int:
        """
        Get the next version number for a chunk.
        
        Args:
            chunk_id: Unique identifier of the chunk.
        
        Returns:
            Next version number (1 if no versions exist).
        """
        query = """
            SELECT MAX(version_number) as max_version
            FROM chunk_versions
            WHERE chunk_id = ?
        """
        results = self.db_connection.execute_query(query, (chunk_id,))
        
        if results and results[0]["max_version"] is not None:
            return results[0]["max_version"] + 1
        return 1
    
    def _generate_change_summary(
        self,
        old_text: str,
        new_text: str
    ) -> str:
        """
        Generate a summary of changes between two text versions.
        
        Args:
            old_text: Previous version text.
            new_text: New version text.
        
        Returns:
            Human-readable summary of changes.
        """
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        
        added = 0
        removed = 0
        modified = 0
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "insert":
                added += j2 - j1
            elif tag == "delete":
                removed += i2 - i1
            elif tag == "replace":
                modified += max(i2 - i1, j2 - j1)
        
        parts = []
        if added > 0:
            parts.append(f"{added} line(s) added")
        if removed > 0:
            parts.append(f"{removed} line(s) removed")
        if modified > 0:
            parts.append(f"{modified} line(s) modified")
        
        if not parts:
            return "No changes detected"
        
        return ", ".join(parts)
    
    def batch_create_versions(
        self,
        versions_data: List[Dict[str, Any]]
    ) -> int:
        """
        Create multiple chunk versions in a batch.
        
        Args:
            versions_data: List of dictionaries containing version data.
                Each dict should have: chunk_id, file_id, chunk_text,
                extraction_strategy, and optionally: raw_source_data,
                start_row, end_row, change_summary.
        
        Returns:
            Number of versions created.
        
        Raises:
            ChunkViewerError: If batch creation fails.
        """
        if not versions_data:
            return 0
        
        try:
            query = """
                INSERT INTO chunk_versions (
                    chunk_id, file_id, version_number, chunk_text, raw_source_data,
                    start_row, end_row, extraction_strategy, indexed_at, change_summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            now = datetime.now().isoformat()
            params_list: List[Tuple[Any, ...]] = []
            
            for data in versions_data:
                chunk_id = data["chunk_id"]
                next_version = self._get_next_version_number(chunk_id)
                
                params_list.append((
                    chunk_id,
                    data["file_id"],
                    next_version,
                    data["chunk_text"],
                    data.get("raw_source_data"),
                    data.get("start_row"),
                    data.get("end_row"),
                    data["extraction_strategy"],
                    now,
                    data.get("change_summary"),
                ))
            
            rows_affected = self.db_connection.execute_many(query, params_list)
            logger.info(f"Batch created {rows_affected} chunk versions")
            return rows_affected
            
        except Exception as e:
            logger.error(f"Failed to batch create versions: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to batch create versions: {e}",
                details={"version_count": len(versions_data)}
            )
