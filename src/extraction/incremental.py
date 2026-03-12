"""
Incremental indexing for efficient file re-indexing.

This module provides incremental indexing capabilities that detect file
modifications using checksums and identify which chunks need updating,
avoiding full re-indexing when only parts of a file have changed.

Supports Requirements:
- 39.1: Detect file modifications using checksums
- 39.2: Identify which chunks need updating
- 39.3: Support forced full re-indexing option
- 39.4: Track modification timestamps
- 39.5: Efficient delta detection
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Protocol

from src.exceptions import IndexingError


logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================

class FileChangeType(str, Enum):
    """Type of change detected in a file."""
    NO_CHANGE = "no_change"
    CONTENT_MODIFIED = "content_modified"
    METADATA_MODIFIED = "metadata_modified"
    NEW_FILE = "new_file"
    DELETED = "deleted"


class ChunkChangeType(str, Enum):
    """Type of change detected in a chunk."""
    NO_CHANGE = "no_change"
    MODIFIED = "modified"
    ADDED = "added"
    REMOVED = "removed"


# Default buffer size for checksum calculation (64KB)
DEFAULT_CHECKSUM_BUFFER_SIZE = 65536


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class FileChecksum:
    """
    Checksum information for a file.
    
    Attributes:
        file_id: Unique identifier for the file.
        file_path: Path to the file.
        md5_checksum: MD5 hash of file content.
        sha256_checksum: SHA-256 hash for stronger verification.
        file_size: File size in bytes.
        modified_time: Last modification timestamp.
        computed_at: When the checksum was computed.
    """
    file_id: str
    file_path: str
    md5_checksum: str
    sha256_checksum: str
    file_size: int
    modified_time: datetime
    computed_at: datetime = field(default_factory=datetime.utcnow)
    
    def matches(self, other: "FileChecksum") -> bool:
        """
        Check if this checksum matches another.
        
        Args:
            other: Another FileChecksum to compare.
            
        Returns:
            True if checksums match.
        """
        return (
            self.md5_checksum == other.md5_checksum
            and self.sha256_checksum == other.sha256_checksum
            and self.file_size == other.file_size
        )


@dataclass
class ChunkChecksum:
    """
    Checksum information for a chunk.
    
    Attributes:
        chunk_id: Unique identifier for the chunk.
        file_id: ID of the parent file.
        sheet_name: Name of the source sheet.
        start_row: Starting row of the chunk.
        end_row: Ending row of the chunk.
        content_hash: Hash of chunk content.
        row_count: Number of rows in the chunk.
        computed_at: When the checksum was computed.
    """
    chunk_id: str
    file_id: str
    sheet_name: str
    start_row: int
    end_row: int
    content_hash: str
    row_count: int
    computed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FileChangeResult:
    """
    Result of file change detection.
    
    Attributes:
        file_id: ID of the file checked.
        file_path: Path to the file.
        change_type: Type of change detected.
        previous_checksum: Previous checksum (if exists).
        current_checksum: Current checksum.
        needs_reindex: Whether the file needs re-indexing.
        reason: Human-readable reason for the result.
    """
    file_id: str
    file_path: str
    change_type: FileChangeType
    previous_checksum: Optional[FileChecksum]
    current_checksum: Optional[FileChecksum]
    needs_reindex: bool
    reason: str


@dataclass
class ChunkChangeResult:
    """
    Result of chunk change detection.
    
    Attributes:
        chunk_id: ID of the chunk.
        file_id: ID of the parent file.
        sheet_name: Name of the source sheet.
        change_type: Type of change detected.
        previous_hash: Previous content hash.
        current_hash: Current content hash.
        needs_update: Whether the chunk needs updating.
    """
    chunk_id: str
    file_id: str
    sheet_name: str
    change_type: ChunkChangeType
    previous_hash: Optional[str]
    current_hash: Optional[str]
    needs_update: bool


@dataclass
class IncrementalIndexingResult:
    """
    Result of incremental indexing analysis.
    
    Attributes:
        file_id: ID of the analyzed file.
        file_change: File-level change result.
        chunk_changes: List of chunk-level changes.
        chunks_to_add: Chunk IDs that need to be added.
        chunks_to_update: Chunk IDs that need updating.
        chunks_to_remove: Chunk IDs that should be removed.
        requires_full_reindex: Whether full re-indexing is needed.
        analysis_time_ms: Time taken for analysis in milliseconds.
    """
    file_id: str
    file_change: FileChangeResult
    chunk_changes: list[ChunkChangeResult] = field(default_factory=list)
    chunks_to_add: list[str] = field(default_factory=list)
    chunks_to_update: list[str] = field(default_factory=list)
    chunks_to_remove: list[str] = field(default_factory=list)
    requires_full_reindex: bool = False
    analysis_time_ms: float = 0.0
    
    @property
    def has_changes(self) -> bool:
        """Check if any changes were detected."""
        return (
            self.file_change.needs_reindex
            or bool(self.chunks_to_add)
            or bool(self.chunks_to_update)
            or bool(self.chunks_to_remove)
        )
    
    @property
    def total_changes(self) -> int:
        """Get total number of chunk changes."""
        return (
            len(self.chunks_to_add)
            + len(self.chunks_to_update)
            + len(self.chunks_to_remove)
        )


# =============================================================================
# Protocols
# =============================================================================

class ChecksumStoreProtocol(Protocol):
    """Protocol for checksum storage."""
    
    def get_file_checksum(self, file_id: str) -> Optional[FileChecksum]:
        """Get stored checksum for a file."""
        ...
    
    def save_file_checksum(self, checksum: FileChecksum) -> None:
        """Save file checksum."""
        ...
    
    def delete_file_checksum(self, file_id: str) -> None:
        """Delete file checksum."""
        ...
    
    def get_chunk_checksums(self, file_id: str) -> list[ChunkChecksum]:
        """Get all chunk checksums for a file."""
        ...
    
    def save_chunk_checksum(self, checksum: ChunkChecksum) -> None:
        """Save chunk checksum."""
        ...
    
    def delete_chunk_checksums(self, file_id: str) -> None:
        """Delete all chunk checksums for a file."""
        ...


# =============================================================================
# Checksum Calculator
# =============================================================================

class ChecksumCalculator:
    """
    Calculates checksums for files and content.
    
    Provides methods for computing MD5 and SHA-256 checksums for files
    and arbitrary content, used for change detection.
    
    Attributes:
        _buffer_size: Buffer size for file reading.
    """
    
    def __init__(
        self,
        buffer_size: int = DEFAULT_CHECKSUM_BUFFER_SIZE
    ) -> None:
        """
        Initialize the checksum calculator.
        
        Args:
            buffer_size: Buffer size for file reading.
        """
        self._buffer_size = buffer_size
        self._logger = logging.getLogger(__name__)
    
    def compute_file_checksum(
        self,
        file_id: str,
        file_path: str
    ) -> FileChecksum:
        """
        Compute checksums for a file.
        
        Args:
            file_id: Unique identifier for the file.
            file_path: Path to the file.
            
        Returns:
            FileChecksum with computed hashes.
            
        Raises:
            IndexingError: If file cannot be read.
        
        Supports Requirement 39.1: Detect file modifications using checksums.
        """
        try:
            md5_hash = hashlib.md5()
            sha256_hash = hashlib.sha256()
            
            with open(file_path, "rb") as f:
                while chunk := f.read(self._buffer_size):
                    md5_hash.update(chunk)
                    sha256_hash.update(chunk)
            
            stat = os.stat(file_path)
            
            return FileChecksum(
                file_id=file_id,
                file_path=file_path,
                md5_checksum=md5_hash.hexdigest(),
                sha256_checksum=sha256_hash.hexdigest(),
                file_size=stat.st_size,
                modified_time=datetime.fromtimestamp(stat.st_mtime),
                computed_at=datetime.utcnow()
            )
            
        except OSError as e:
            self._logger.error(f"Failed to compute checksum for {file_path}: {e}")
            raise IndexingError(
                f"Failed to compute file checksum: {e}",
                details={"file_path": file_path, "error": str(e)}
            )
    
    def compute_content_hash(self, content: Any) -> str:
        """
        Compute hash for arbitrary content.
        
        Args:
            content: Content to hash (will be converted to string).
            
        Returns:
            SHA-256 hash of the content.
        """
        content_str = str(content)
        return hashlib.sha256(content_str.encode("utf-8")).hexdigest()
    
    def compute_chunk_checksum(
        self,
        chunk_id: str,
        file_id: str,
        sheet_name: str,
        start_row: int,
        end_row: int,
        content: list[list[Any]]
    ) -> ChunkChecksum:
        """
        Compute checksum for a chunk.
        
        Args:
            chunk_id: Unique identifier for the chunk.
            file_id: ID of the parent file.
            sheet_name: Name of the source sheet.
            start_row: Starting row of the chunk.
            end_row: Ending row of the chunk.
            content: Chunk content as list of rows.
            
        Returns:
            ChunkChecksum with computed hash.
        """
        content_hash = self.compute_content_hash(content)
        
        return ChunkChecksum(
            chunk_id=chunk_id,
            file_id=file_id,
            sheet_name=sheet_name,
            start_row=start_row,
            end_row=end_row,
            content_hash=content_hash,
            row_count=len(content),
            computed_at=datetime.utcnow()
        )


# =============================================================================
# In-Memory Checksum Store
# =============================================================================

class InMemoryChecksumStore:
    """
    In-memory implementation of checksum storage.
    
    Stores checksums in memory for testing and development.
    For production, use a database-backed implementation.
    
    Attributes:
        _file_checksums: Dictionary of file checksums.
        _chunk_checksums: Dictionary of chunk checksums by file.
    """
    
    def __init__(self) -> None:
        """Initialize the in-memory store."""
        self._file_checksums: dict[str, FileChecksum] = {}
        self._chunk_checksums: dict[str, list[ChunkChecksum]] = {}
    
    def get_file_checksum(self, file_id: str) -> Optional[FileChecksum]:
        """Get stored checksum for a file."""
        return self._file_checksums.get(file_id)
    
    def save_file_checksum(self, checksum: FileChecksum) -> None:
        """Save file checksum."""
        self._file_checksums[checksum.file_id] = checksum
    
    def delete_file_checksum(self, file_id: str) -> None:
        """Delete file checksum."""
        self._file_checksums.pop(file_id, None)
    
    def get_chunk_checksums(self, file_id: str) -> list[ChunkChecksum]:
        """Get all chunk checksums for a file."""
        return self._chunk_checksums.get(file_id, [])
    
    def save_chunk_checksum(self, checksum: ChunkChecksum) -> None:
        """Save chunk checksum."""
        if checksum.file_id not in self._chunk_checksums:
            self._chunk_checksums[checksum.file_id] = []
        self._chunk_checksums[checksum.file_id].append(checksum)
    
    def delete_chunk_checksums(self, file_id: str) -> None:
        """Delete all chunk checksums for a file."""
        self._chunk_checksums.pop(file_id, None)
    
    def clear(self) -> None:
        """Clear all stored checksums."""
        self._file_checksums.clear()
        self._chunk_checksums.clear()


# =============================================================================
# Incremental Indexing Service
# =============================================================================

class IncrementalIndexingService:
    """
    Service for incremental indexing with change detection.
    
    Detects file and chunk modifications using checksums to enable
    efficient incremental re-indexing instead of full re-indexing.
    
    All dependencies are injected via constructor following DIP.
    
    Attributes:
        _checksum_calculator: Calculator for computing checksums.
        _checksum_store: Storage for checksums.
        _logger: Logger instance.
    
    Example:
        >>> calculator = ChecksumCalculator()
        >>> store = InMemoryChecksumStore()
        >>> service = IncrementalIndexingService(calculator, store)
        >>> result = service.analyze_file("file_123", "/path/to/file.xlsx")
        >>> if result.has_changes:
        ...     process_changes(result)
    
    Supports Requirements 39.1, 39.2, 39.3, 39.4, 39.5.
    """
    
    def __init__(
        self,
        checksum_calculator: Optional[ChecksumCalculator] = None,
        checksum_store: Optional[ChecksumStoreProtocol] = None
    ) -> None:
        """
        Initialize the incremental indexing service.
        
        Args:
            checksum_calculator: Calculator for computing checksums.
            checksum_store: Storage for checksums.
        """
        self._checksum_calculator = checksum_calculator or ChecksumCalculator()
        self._checksum_store = checksum_store or InMemoryChecksumStore()
        self._logger = logging.getLogger(__name__)
    
    def analyze_file(
        self,
        file_id: str,
        file_path: str,
        force_full_reindex: bool = False
    ) -> IncrementalIndexingResult:
        """
        Analyze a file for changes and determine indexing needs.
        
        Computes current checksum and compares with stored checksum
        to detect modifications. Returns analysis result indicating
        what needs to be re-indexed.
        
        Args:
            file_id: Unique identifier for the file.
            file_path: Path to the file.
            force_full_reindex: If True, always require full re-indexing.
            
        Returns:
            IncrementalIndexingResult with change analysis.
        
        Supports Requirements 39.1, 39.2, 39.3.
        """
        import time
        start_time = time.time()
        
        self._logger.debug(f"Analyzing file {file_id} for changes")
        
        # Handle forced full re-index
        if force_full_reindex:
            self._logger.info(f"Forced full re-index requested for {file_id}")
            return self._create_full_reindex_result(
                file_id, file_path, "Forced full re-index requested"
            )
        
        # Check if file exists
        if not os.path.exists(file_path):
            return self._create_deleted_result(file_id, file_path)
        
        # Compute current checksum
        try:
            current_checksum = self._checksum_calculator.compute_file_checksum(
                file_id, file_path
            )
        except IndexingError as e:
            self._logger.error(f"Failed to compute checksum: {e}")
            return self._create_full_reindex_result(
                file_id, file_path, f"Checksum computation failed: {e}"
            )
        
        # Get previous checksum
        previous_checksum = self._checksum_store.get_file_checksum(file_id)
        
        # Determine change type
        file_change = self._detect_file_change(
            file_id, file_path, previous_checksum, current_checksum
        )
        
        # Build result
        analysis_time_ms = (time.time() - start_time) * 1000
        
        result = IncrementalIndexingResult(
            file_id=file_id,
            file_change=file_change,
            requires_full_reindex=file_change.needs_reindex,
            analysis_time_ms=analysis_time_ms
        )
        
        self._logger.info(
            f"File analysis complete for {file_id}: "
            f"change_type={file_change.change_type.value}, "
            f"needs_reindex={file_change.needs_reindex}"
        )
        
        return result
    
    def analyze_chunks(
        self,
        file_id: str,
        current_chunks: list[tuple[str, str, int, int, list[list[Any]]]]
    ) -> list[ChunkChangeResult]:
        """
        Analyze chunks for changes.
        
        Compares current chunk content with stored checksums to identify
        which chunks have been modified, added, or removed.
        
        Args:
            file_id: ID of the parent file.
            current_chunks: List of tuples containing:
                (chunk_id, sheet_name, start_row, end_row, content)
            
        Returns:
            List of ChunkChangeResult for each chunk.
        
        Supports Requirement 39.2: Identify which chunks need updating.
        """
        results: list[ChunkChangeResult] = []
        
        # Get previous chunk checksums
        previous_checksums = {
            cs.chunk_id: cs
            for cs in self._checksum_store.get_chunk_checksums(file_id)
        }
        
        current_chunk_ids = set()
        
        # Analyze each current chunk
        for chunk_id, sheet_name, start_row, end_row, content in current_chunks:
            current_chunk_ids.add(chunk_id)
            
            current_hash = self._checksum_calculator.compute_content_hash(content)
            previous = previous_checksums.get(chunk_id)
            
            if previous is None:
                # New chunk
                results.append(ChunkChangeResult(
                    chunk_id=chunk_id,
                    file_id=file_id,
                    sheet_name=sheet_name,
                    change_type=ChunkChangeType.ADDED,
                    previous_hash=None,
                    current_hash=current_hash,
                    needs_update=True
                ))
            elif previous.content_hash != current_hash:
                # Modified chunk
                results.append(ChunkChangeResult(
                    chunk_id=chunk_id,
                    file_id=file_id,
                    sheet_name=sheet_name,
                    change_type=ChunkChangeType.MODIFIED,
                    previous_hash=previous.content_hash,
                    current_hash=current_hash,
                    needs_update=True
                ))
            else:
                # No change
                results.append(ChunkChangeResult(
                    chunk_id=chunk_id,
                    file_id=file_id,
                    sheet_name=sheet_name,
                    change_type=ChunkChangeType.NO_CHANGE,
                    previous_hash=previous.content_hash,
                    current_hash=current_hash,
                    needs_update=False
                ))
        
        # Check for removed chunks
        for chunk_id, checksum in previous_checksums.items():
            if chunk_id not in current_chunk_ids:
                results.append(ChunkChangeResult(
                    chunk_id=chunk_id,
                    file_id=file_id,
                    sheet_name=checksum.sheet_name,
                    change_type=ChunkChangeType.REMOVED,
                    previous_hash=checksum.content_hash,
                    current_hash=None,
                    needs_update=True
                ))
        
        return results
    
    def update_checksums(
        self,
        file_checksum: FileChecksum,
        chunk_checksums: list[ChunkChecksum]
    ) -> None:
        """
        Update stored checksums after successful indexing.
        
        Args:
            file_checksum: New file checksum to store.
            chunk_checksums: New chunk checksums to store.
        
        Supports Requirement 39.4: Track modification timestamps.
        """
        # Clear old chunk checksums
        self._checksum_store.delete_chunk_checksums(file_checksum.file_id)
        
        # Save new checksums
        self._checksum_store.save_file_checksum(file_checksum)
        
        for chunk_checksum in chunk_checksums:
            self._checksum_store.save_chunk_checksum(chunk_checksum)
        
        self._logger.debug(
            f"Updated checksums for file {file_checksum.file_id}: "
            f"{len(chunk_checksums)} chunks"
        )
    
    def clear_checksums(self, file_id: str) -> None:
        """
        Clear all checksums for a file.
        
        Args:
            file_id: ID of the file to clear checksums for.
        """
        self._checksum_store.delete_file_checksum(file_id)
        self._checksum_store.delete_chunk_checksums(file_id)
        self._logger.debug(f"Cleared checksums for file {file_id}")
    
    def _detect_file_change(
        self,
        file_id: str,
        file_path: str,
        previous: Optional[FileChecksum],
        current: FileChecksum
    ) -> FileChangeResult:
        """
        Detect the type of change for a file.
        
        Args:
            file_id: ID of the file.
            file_path: Path to the file.
            previous: Previous checksum (if exists).
            current: Current checksum.
            
        Returns:
            FileChangeResult with detected change type.
        """
        if previous is None:
            return FileChangeResult(
                file_id=file_id,
                file_path=file_path,
                change_type=FileChangeType.NEW_FILE,
                previous_checksum=None,
                current_checksum=current,
                needs_reindex=True,
                reason="New file, not previously indexed"
            )
        
        if previous.matches(current):
            # Check if only metadata changed
            if previous.modified_time != current.modified_time:
                return FileChangeResult(
                    file_id=file_id,
                    file_path=file_path,
                    change_type=FileChangeType.METADATA_MODIFIED,
                    previous_checksum=previous,
                    current_checksum=current,
                    needs_reindex=False,
                    reason="Only metadata changed, content unchanged"
                )
            
            return FileChangeResult(
                file_id=file_id,
                file_path=file_path,
                change_type=FileChangeType.NO_CHANGE,
                previous_checksum=previous,
                current_checksum=current,
                needs_reindex=False,
                reason="No changes detected"
            )
        
        return FileChangeResult(
            file_id=file_id,
            file_path=file_path,
            change_type=FileChangeType.CONTENT_MODIFIED,
            previous_checksum=previous,
            current_checksum=current,
            needs_reindex=True,
            reason="Content has been modified"
        )
    
    def _create_full_reindex_result(
        self,
        file_id: str,
        file_path: str,
        reason: str
    ) -> IncrementalIndexingResult:
        """Create result indicating full re-index is needed."""
        return IncrementalIndexingResult(
            file_id=file_id,
            file_change=FileChangeResult(
                file_id=file_id,
                file_path=file_path,
                change_type=FileChangeType.CONTENT_MODIFIED,
                previous_checksum=None,
                current_checksum=None,
                needs_reindex=True,
                reason=reason
            ),
            requires_full_reindex=True
        )
    
    def _create_deleted_result(
        self,
        file_id: str,
        file_path: str
    ) -> IncrementalIndexingResult:
        """Create result for a deleted file."""
        previous = self._checksum_store.get_file_checksum(file_id)
        
        return IncrementalIndexingResult(
            file_id=file_id,
            file_change=FileChangeResult(
                file_id=file_id,
                file_path=file_path,
                change_type=FileChangeType.DELETED,
                previous_checksum=previous,
                current_checksum=None,
                needs_reindex=False,
                reason="File has been deleted"
            ),
            requires_full_reindex=False
        )


# =============================================================================
# Factory Function
# =============================================================================

def create_incremental_indexing_service(
    checksum_store: Optional[ChecksumStoreProtocol] = None
) -> IncrementalIndexingService:
    """
    Create an incremental indexing service.
    
    Factory function for creating IncrementalIndexingService with
    default or custom checksum storage.
    
    Args:
        checksum_store: Optional custom checksum storage.
            Uses InMemoryChecksumStore if not provided.
            
    Returns:
        Configured IncrementalIndexingService instance.
    """
    calculator = ChecksumCalculator()
    store = checksum_store or InMemoryChecksumStore()
    
    return IncrementalIndexingService(calculator, store)
