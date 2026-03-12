"""
Data Lineage Tracker

This module provides high-level tracking of data lineage from source Excel
cells to answer components. It creates lineage records, tracks timestamps,
and implements staleness detection when source data changes.

Key Features:
- Create lineage records linking answers to sources
- Track indexed_at and last_verified_at timestamps
- Implement staleness detection when source data changes
- Support verification of lineage accuracy

Requirements: 17.1, 17.2, 17.3, 17.4, 17.5
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from src.exceptions import LineageError
from src.models.traceability import DataLineage
from src.traceability.lineage_storage import LineageStorage

logger = logging.getLogger(__name__)


@dataclass
class SourceInfo:
    """
    Information about a source cell or range in an Excel file.
    
    Attributes:
        file_id: ID of the source file.
        file_name: Name of the source file.
        sheet_name: Name of the source sheet.
        cell_range: Cell range containing the source data (e.g., "A1:B10").
        source_value: The actual value from the source cell(s).
    """
    file_id: str
    file_name: str
    sheet_name: str
    cell_range: str
    source_value: str


class FileMonitorProtocol(Protocol):
    """Protocol for file modification monitoring."""
    
    def get_file_modified_time(self, file_id: str) -> Optional[datetime]:
        """Get the last modified time for a file."""
        ...
    
    def get_file_checksum(self, file_id: str) -> Optional[str]:
        """Get the checksum for a file."""
        ...


class DataLineageTracker:
    """
    Tracks data lineage from source Excel cells to answer components.
    
    Creates and manages lineage records that enable compliance officers
    to verify data accuracy and meet audit requirements. Implements
    staleness detection when source data changes.
    
    Attributes:
        storage: Injected LineageStorage for persisting lineage records.
        file_monitor: Optional file monitor for staleness detection.
    
    Requirements: 17.1, 17.2, 17.3, 17.4, 17.5
    """
    
    def __init__(
        self,
        storage: LineageStorage,
        file_monitor: Optional[FileMonitorProtocol] = None,
    ) -> None:
        """
        Initialize the data lineage tracker.
        
        Args:
            storage: LineageStorage instance for persisting lineage records.
            file_monitor: Optional file monitor for staleness detection.
        
        Raises:
            LineageError: If storage is None.
        """
        if storage is None:
            raise LineageError(
                "LineageStorage is required",
                details={"parameter": "storage"}
            )
        
        self.storage = storage
        self.file_monitor = file_monitor
        logger.info("DataLineageTracker initialized")

    def create_lineage(
        self,
        trace_id: str,
        answer_component: str,
        source_info: SourceInfo,
        chunk_id: str,
        embedding_id: str,
        retrieval_score: float,
        indexed_at: Optional[str] = None,
    ) -> str:
        """
        Create a lineage record linking an answer component to its source.
        
        Args:
            trace_id: The trace ID this lineage belongs to.
            answer_component: The part of the answer this lineage relates to.
            source_info: Information about the source cell/range.
            chunk_id: ID of the chunk containing this data.
            embedding_id: ID of the embedding for this chunk.
            retrieval_score: Similarity score when this chunk was retrieved.
            indexed_at: Optional timestamp when source was indexed.
        
        Returns:
            The generated lineage_id.
        
        Raises:
            LineageError: If lineage creation fails.
        
        Requirements: 17.1, 17.2
        """
        try:
            lineage_id = f"lin_{uuid.uuid4().hex[:16]}"
            now = datetime.now().isoformat()
            
            lineage = DataLineage(
                lineage_id=lineage_id,
                answer_component=answer_component,
                file_id=source_info.file_id,
                file_name=source_info.file_name,
                sheet_name=source_info.sheet_name,
                cell_range=source_info.cell_range,
                source_value=source_info.source_value,
                chunk_id=chunk_id,
                embedding_id=embedding_id,
                retrieval_score=retrieval_score,
                indexed_at=indexed_at or now,
                last_verified_at=None,
                is_stale=False,
                stale_reason=None,
            )
            
            self.storage.create_lineage(lineage, trace_id)
            
            logger.debug(
                f"Created lineage {lineage_id} for trace {trace_id}: "
                f"file={source_info.file_name}, range={source_info.cell_range}"
            )
            
            return lineage_id
            
        except LineageError:
            raise
        except Exception as e:
            logger.error(f"Failed to create lineage: {e}", exc_info=True)
            raise LineageError(
                f"Failed to create lineage: {e}",
                details={"trace_id": trace_id, "answer_component": answer_component}
            )

    def batch_create_lineages(
        self,
        trace_id: str,
        lineage_data: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Create multiple lineage records in a batch.
        
        Args:
            trace_id: The trace ID these lineages belong to.
            lineage_data: List of dictionaries containing lineage data.
                Each dict should have: answer_component, source_info,
                chunk_id, embedding_id, retrieval_score, and optionally indexed_at.
        
        Returns:
            List of generated lineage_ids.
        
        Raises:
            LineageError: If batch creation fails.
        
        Requirements: 17.1
        """
        try:
            now = datetime.now().isoformat()
            lineages: List[DataLineage] = []
            lineage_ids: List[str] = []
            
            for data in lineage_data:
                lineage_id = f"lin_{uuid.uuid4().hex[:16]}"
                lineage_ids.append(lineage_id)
                
                source_info = data["source_info"]
                
                lineage = DataLineage(
                    lineage_id=lineage_id,
                    answer_component=data["answer_component"],
                    file_id=source_info.file_id,
                    file_name=source_info.file_name,
                    sheet_name=source_info.sheet_name,
                    cell_range=source_info.cell_range,
                    source_value=source_info.source_value,
                    chunk_id=data["chunk_id"],
                    embedding_id=data["embedding_id"],
                    retrieval_score=data["retrieval_score"],
                    indexed_at=data.get("indexed_at", now),
                    last_verified_at=None,
                    is_stale=False,
                    stale_reason=None,
                )
                lineages.append(lineage)
            
            self.storage.batch_create_lineages(lineages, trace_id)
            
            logger.debug(
                f"Batch created {len(lineages)} lineages for trace {trace_id}"
            )
            
            return lineage_ids
            
        except LineageError:
            raise
        except Exception as e:
            logger.error(f"Failed to batch create lineages: {e}", exc_info=True)
            raise LineageError(
                f"Failed to batch create lineages: {e}",
                details={"trace_id": trace_id, "count": len(lineage_data)}
            )

    def get_lineage(self, lineage_id: str) -> Optional[DataLineage]:
        """
        Retrieve a lineage record by ID.
        
        Args:
            lineage_id: The lineage identifier.
        
        Returns:
            DataLineage object or None if not found.
        
        Raises:
            LineageError: If retrieval fails.
        
        Requirements: 17.3
        """
        return self.storage.get_lineage(lineage_id)

    def get_lineages_for_trace(self, trace_id: str) -> List[DataLineage]:
        """
        Retrieve all lineage records for a trace.
        
        Args:
            trace_id: The trace identifier.
        
        Returns:
            List of DataLineage objects.
        
        Raises:
            LineageError: If retrieval fails.
        """
        return self.storage.get_lineages_by_trace(trace_id)

    def check_staleness(self, lineage_id: str) -> bool:
        """
        Check if a lineage record is stale.
        
        A lineage is considered stale if the source file has been modified
        since the data was indexed. Requires a file_monitor to be configured.
        
        Args:
            lineage_id: The lineage identifier.
        
        Returns:
            True if lineage is stale, False otherwise.
        
        Raises:
            LineageError: If staleness check fails.
        
        Requirements: 17.4, 17.5
        """
        try:
            lineage = self.storage.get_lineage(lineage_id)
            
            if lineage is None:
                raise LineageError(
                    f"Lineage not found: {lineage_id}",
                    details={"lineage_id": lineage_id}
                )
            
            # If already marked stale, return True
            if lineage.is_stale:
                return True
            
            # If no file monitor, cannot check staleness
            if self.file_monitor is None:
                return False
            
            # Get file modification time
            modified_time = self.file_monitor.get_file_modified_time(
                lineage.file_id
            )
            
            if modified_time is None:
                # File not found - mark as stale
                self._mark_stale(
                    lineage_id,
                    "Source file no longer exists"
                )
                return True
            
            # Parse indexed_at timestamp
            indexed_at = datetime.fromisoformat(lineage.indexed_at)
            
            # Check if file was modified after indexing
            if modified_time > indexed_at:
                self._mark_stale(
                    lineage_id,
                    f"Source file modified at {modified_time.isoformat()}"
                )
                return True
            
            return False
            
        except LineageError:
            raise
        except Exception as e:
            logger.error(f"Failed to check staleness: {e}", exc_info=True)
            raise LineageError(
                f"Failed to check staleness: {e}",
                details={"lineage_id": lineage_id}
            )

    def verify_lineage(self, lineage_id: str) -> bool:
        """
        Verify a lineage record and update last_verified_at timestamp.
        
        This should be called after confirming the source data is still
        accurate. Updates the last_verified_at timestamp.
        
        Args:
            lineage_id: The lineage identifier.
        
        Returns:
            True if verification was successful, False if lineage not found.
        
        Raises:
            LineageError: If verification fails.
        
        Requirements: 17.4
        """
        try:
            now = datetime.now().isoformat()
            
            success = self.storage.update_lineage(
                lineage_id,
                {"last_verified_at": now}
            )
            
            if success:
                logger.debug(f"Verified lineage: {lineage_id}")
            
            return success
            
        except LineageError:
            raise
        except Exception as e:
            logger.error(f"Failed to verify lineage: {e}", exc_info=True)
            raise LineageError(
                f"Failed to verify lineage: {e}",
                details={"lineage_id": lineage_id}
            )

    def _mark_stale(self, lineage_id: str, reason: str) -> None:
        """Mark a lineage record as stale with a reason."""
        self.storage.update_lineage(
            lineage_id,
            {"is_stale": True, "stale_reason": reason}
        )
        logger.debug(f"Marked lineage {lineage_id} as stale: {reason}")

    def mark_file_lineages_stale(
        self,
        file_id: str,
        reason: str,
    ) -> int:
        """
        Mark all lineage records for a file as stale.
        
        Use this when a file has been re-indexed or modified.
        
        Args:
            file_id: The file identifier.
            reason: Explanation of why records are marked stale.
        
        Returns:
            Number of lineage records marked as stale.
        
        Raises:
            LineageError: If marking fails.
        
        Requirements: 17.5
        """
        return self.storage.mark_stale_by_file(file_id, reason)

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
        return self.storage.get_stale_lineages(limit)

    def clear_staleness(self, lineage_id: str) -> bool:
        """
        Clear the stale flag on a lineage record.
        
        Use this after re-verifying the source data is accurate.
        
        Args:
            lineage_id: The lineage identifier.
        
        Returns:
            True if successful, False if lineage not found.
        
        Raises:
            LineageError: If update fails.
        """
        now = datetime.now().isoformat()
        return self.storage.update_lineage(
            lineage_id,
            {
                "is_stale": False,
                "stale_reason": None,
                "last_verified_at": now,
            }
        )
