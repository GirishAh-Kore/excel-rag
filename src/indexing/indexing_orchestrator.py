"""
Indexing Orchestrator

This module orchestrates the end-to-end indexing process for Excel files from Google Drive.
It manages full and incremental indexing, parallel processing, state tracking, and pause/resume functionality.
"""

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Set
from threading import Lock, Event

from src.gdrive.connector import GoogleDriveConnector
from src.extraction.configurable_extractor import ConfigurableExtractor
from src.database.connection import DatabaseConnection
from src.models.domain_models import FileMetadata, FileStatus, IndexingReport
from src.utils.metrics import increment_counter, set_gauge, timer
from src.utils.logging_config import get_logger


logger = get_logger(__name__)


class IndexingState(Enum):
    """Indexing state enumeration"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IndexingProgress:
    """Tracks indexing progress in real-time"""
    total_files: int = 0
    files_processed: int = 0
    files_failed: int = 0
    files_skipped: int = 0
    current_file: Optional[str] = None
    state: IndexingState = IndexingState.IDLE
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage"""
        if self.total_files == 0:
            return 0.0
        return (self.files_processed + self.files_failed + self.files_skipped) / self.total_files * 100
    
    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds"""
        if not self.start_time:
            return 0.0
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()


class IndexingOrchestrator:
    """
    Orchestrates the indexing pipeline for Excel files.
    
    Responsibilities:
    - Coordinate full and incremental indexing workflows
    - Manage parallel processing of files
    - Track indexing state in database
    - Support pause/resume functionality
    - Generate progress reports
    """
    
    def __init__(
        self,
        gdrive_connector: GoogleDriveConnector,
        content_extractor: ConfigurableExtractor,
        db_connection: DatabaseConnection,
        max_workers: int = 5
    ):
        """
        Initialize the indexing orchestrator.
        
        Args:
            gdrive_connector: Google Drive connector for file operations
            content_extractor: Content extractor for parsing Excel files
            db_connection: Database connection for metadata storage
            max_workers: Maximum number of concurrent workers (default: 5)
        """
        self.gdrive_connector = gdrive_connector
        self.content_extractor = content_extractor
        self.db_connection = db_connection
        self.max_workers = max_workers
        
        # Progress tracking
        self.progress = IndexingProgress()
        self.progress_lock = Lock()
        
        # Pause/resume control
        self.pause_event = Event()
        self.pause_event.set()  # Not paused by default
        self.stop_event = Event()
        
        # Job tracking for local file indexing
        self._active_jobs: Dict[str, Dict[str, Any]] = {}
        self._completed_jobs: Dict[str, Dict[str, Any]] = {}
        self._failed_jobs: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"IndexingOrchestrator initialized with max_workers={max_workers}")
    
    def full_index(self) -> IndexingReport:
        """
        Perform complete indexing of all Excel files in Google Drive.
        
        Returns:
            IndexingReport with summary statistics
        """
        logger.info("Starting full indexing")
        start_time = time.time()
        
        try:
            # Reset state
            self._reset_progress()
            self.progress.state = IndexingState.RUNNING
            self.progress.start_time = datetime.now()
            
            increment_counter('indexing.full_index_started')
            
            # List all Excel files from Google Drive
            logger.info("Listing Excel files from Google Drive")
            files = self.gdrive_connector.list_excel_files()
            
            with self.progress_lock:
                self.progress.total_files = len(files)
            
            set_gauge('indexing.total_files', len(files))
            logger.info(f"Found {len(files)} Excel files to index")
            
            # Process files in parallel
            self._process_files_parallel(files, force_reindex=False)
            
            # Mark as completed
            with self.progress_lock:
                self.progress.state = IndexingState.COMPLETED
                self.progress.end_time = datetime.now()
            
            # Calculate throughput (files per minute)
            duration_seconds = time.time() - start_time
            if duration_seconds > 0:
                throughput = (self.progress.files_processed / duration_seconds) * 60
                set_gauge('indexing.throughput_files_per_minute', throughput)
            
            # Generate report
            report = self._generate_report()
            increment_counter('indexing.full_index_completed')
            logger.info(f"Full indexing completed: {report}")
            
            return report
            
        except Exception as e:
            logger.error(f"Full indexing failed: {e}", exc_info=True)
            increment_counter('indexing.full_index_failed')
            with self.progress_lock:
                self.progress.state = IndexingState.FAILED
                self.progress.errors.append(f"Full indexing failed: {str(e)}")
            raise
    
    def incremental_index(self) -> IndexingReport:
        """
        Perform incremental indexing of only new or modified files.
        
        Uses MD5 checksums to detect changes and only processes files that:
        - Are new (not in database)
        - Have been modified (MD5 checksum changed)
        - Were previously failed
        
        Returns:
            IndexingReport with summary statistics
        """
        logger.info("Starting incremental indexing")
        start_time = time.time()
        
        try:
            # Reset state
            self._reset_progress()
            self.progress.state = IndexingState.RUNNING
            self.progress.start_time = datetime.now()
            
            increment_counter('indexing.incremental_index_started')
            
            # List all Excel files from Google Drive
            logger.info("Listing Excel files from Google Drive")
            current_files = self.gdrive_connector.list_excel_files()
            
            # Get indexed files from database
            indexed_files = self._get_indexed_files()
            
            # Identify files to process
            files_to_process = self._identify_changed_files(current_files, indexed_files)
            
            # Identify deleted files
            deleted_files = self._identify_deleted_files(current_files, indexed_files)
            
            with self.progress_lock:
                self.progress.total_files = len(files_to_process)
            
            set_gauge('indexing.files_to_process', len(files_to_process))
            set_gauge('indexing.files_to_delete', len(deleted_files))
            logger.info(f"Found {len(files_to_process)} files to process, {len(deleted_files)} files to remove")
            
            # Remove deleted files from index
            for file_id in deleted_files:
                self._remove_file_from_index(file_id)
                increment_counter('indexing.files_deleted')
            
            # Process changed files in parallel
            if files_to_process:
                self._process_files_parallel(files_to_process, force_reindex=False)
            
            # Mark as completed
            with self.progress_lock:
                self.progress.state = IndexingState.COMPLETED
                self.progress.end_time = datetime.now()
            
            # Calculate throughput (files per minute)
            duration_seconds = time.time() - start_time
            if duration_seconds > 0 and self.progress.files_processed > 0:
                throughput = (self.progress.files_processed / duration_seconds) * 60
                set_gauge('indexing.throughput_files_per_minute', throughput)
            
            # Generate report
            report = self._generate_report()
            increment_counter('indexing.incremental_index_completed')
            logger.info(f"Incremental indexing completed: {report}")
            
            return report
            
        except Exception as e:
            logger.error(f"Incremental indexing failed: {e}", exc_info=True)
            increment_counter('indexing.incremental_index_failed')
            with self.progress_lock:
                self.progress.state = IndexingState.FAILED
                self.progress.errors.append(f"Incremental indexing failed: {str(e)}")
            raise
    
    def index_file(self, file_id: str, force: bool = False) -> bool:
        """
        Index a specific file by ID.
        
        Args:
            file_id: Google Drive file ID
            force: Force reindexing even if file hasn't changed
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Indexing file: {file_id} (force={force})")
        
        try:
            # Get file metadata
            file_metadata = self.gdrive_connector.get_file_metadata(file_id)
            
            # Check if file needs indexing
            if not force and not self._should_index_file(file_metadata):
                logger.info(f"File {file_id} hasn't changed, skipping")
                return True
            
            # Process the file
            return self._process_single_file(file_metadata)
            
        except Exception as e:
            logger.error(f"Failed to index file {file_id}: {e}", exc_info=True)
            return False
    
    def pause(self):
        """Pause the indexing process"""
        logger.info("Pausing indexing")
        self.pause_event.clear()
        with self.progress_lock:
            self.progress.state = IndexingState.PAUSED
    
    def resume(self):
        """Resume the indexing process"""
        logger.info("Resuming indexing")
        self.pause_event.set()
        with self.progress_lock:
            if self.progress.state == IndexingState.PAUSED:
                self.progress.state = IndexingState.RUNNING
    
    def stop(self):
        """Stop the indexing process"""
        logger.info("Stopping indexing")
        self.stop_event.set()
        self.pause_event.set()  # Unblock any waiting threads
    
    def get_progress(self) -> IndexingProgress:
        """Get current indexing progress"""
        with self.progress_lock:
            return IndexingProgress(
                total_files=self.progress.total_files,
                files_processed=self.progress.files_processed,
                files_failed=self.progress.files_failed,
                files_skipped=self.progress.files_skipped,
                current_file=self.progress.current_file,
                state=self.progress.state,
                start_time=self.progress.start_time,
                end_time=self.progress.end_time,
                errors=self.progress.errors.copy()
            )
    
    def _reset_progress(self):
        """Reset progress tracking"""
        with self.progress_lock:
            self.progress = IndexingProgress()
        self.stop_event.clear()
        self.pause_event.set()
    
    def _process_files_parallel(self, files: List[FileMetadata], force_reindex: bool = False):
        """
        Process multiple files in parallel using ThreadPoolExecutor.
        
        Args:
            files: List of file metadata to process
            force_reindex: Force reindexing even if files haven't changed
        """
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all files for processing
            future_to_file = {
                executor.submit(self._process_file_with_controls, file, force_reindex): file
                for file in files
            }
            
            # Process completed futures
            for future in as_completed(future_to_file):
                file = future_to_file[future]
                
                try:
                    success = future.result()
                    if success:
                        logger.debug(f"Successfully processed file: {file.name}")
                    else:
                        logger.warning(f"Failed to process file: {file.name}")
                        
                except Exception as e:
                    logger.error(f"Exception processing file {file.name}: {e}", exc_info=True)
                    with self.progress_lock:
                        self.progress.files_failed += 1
                        self.progress.errors.append(f"{file.name}: {str(e)}")
    
    def _process_file_with_controls(self, file_metadata: FileMetadata, force_reindex: bool) -> bool:
        """
        Process a single file with pause/stop controls.
        
        Args:
            file_metadata: File metadata
            force_reindex: Force reindexing even if file hasn't changed
            
        Returns:
            True if successful, False otherwise
        """
        # Check for stop signal
        if self.stop_event.is_set():
            logger.info("Stop signal received, aborting file processing")
            return False
        
        # Wait if paused
        self.pause_event.wait()
        
        # Check if file needs indexing
        if not force_reindex and not self._should_index_file(file_metadata):
            with self.progress_lock:
                self.progress.files_skipped += 1
            logger.debug(f"Skipping unchanged file: {file_metadata.name}")
            return True
        
        # Process the file
        return self._process_single_file(file_metadata)
    
    def _process_single_file(self, file_metadata: FileMetadata) -> bool:
        """
        Process a single file: download, extract, and store metadata.
        
        Args:
            file_metadata: File metadata
            
        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()
        
        try:
            # Update current file
            with self.progress_lock:
                self.progress.current_file = file_metadata.name
            
            logger.info(f"Processing file: {file_metadata.name}")
            
            # Mark file as pending in database
            self._update_file_status(file_metadata, FileStatus.PENDING)
            
            # Download file content
            with timer('indexing.download_file'):
                file_content = self.gdrive_connector.download_file(file_metadata.file_id)
            
            # Extract workbook data (using synchronous method)
            with timer('indexing.extract_workbook'):
                workbook_data = self.content_extractor.extract_workbook_sync(
                    file_content=file_content,
                    file_name=file_metadata.name,
                    file_id=file_metadata.file_id,
                    file_path=file_metadata.path,
                    modified_time=file_metadata.modified_time
                )
            
            # Store file metadata in database (will be implemented in task 7.4)
            # For now, just mark as indexed
            self._update_file_status(file_metadata, FileStatus.INDEXED)
            
            # Update progress and metrics
            with self.progress_lock:
                self.progress.files_processed += 1
            
            increment_counter('indexing.files_processed')
            increment_counter('indexing.sheets_processed', value=len(workbook_data.sheets))
            
            # Track file processing time
            duration_ms = (time.time() - start_time) * 1000
            from src.utils.metrics import record_timer
            record_timer('indexing.file_processing_time', duration_ms)
            
            logger.info(f"Successfully processed file: {file_metadata.name} ({len(workbook_data.sheets)} sheets)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process file {file_metadata.name}: {e}", exc_info=True)
            
            # Mark file as failed
            self._update_file_status(file_metadata, FileStatus.FAILED)
            
            # Update progress and metrics
            with self.progress_lock:
                self.progress.files_failed += 1
                self.progress.errors.append(f"{file_metadata.name}: {str(e)}")
            
            increment_counter('indexing.files_failed')
            
            return False
    
    def _should_index_file(self, file_metadata: FileMetadata) -> bool:
        """
        Check if a file should be indexed based on MD5 checksum.
        
        Args:
            file_metadata: File metadata
            
        Returns:
            True if file should be indexed, False otherwise
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT md5_checksum, status FROM files WHERE file_id = ?",
                    (file_metadata.file_id,)
                )
                result = cursor.fetchone()
                
                if not result:
                    # New file, should be indexed
                    return True
                
                stored_md5, status = result
                
                # Index if MD5 changed or previous indexing failed
                return stored_md5 != file_metadata.md5_checksum or status == FileStatus.FAILED.value
                
        except Exception as e:
            logger.error(f"Error checking if file should be indexed: {e}")
            # Default to indexing on error
            return True
    
    def _update_file_status(self, file_metadata: FileMetadata, status: FileStatus):
        """
        Update file status in database.
        
        Args:
            file_metadata: File metadata
            status: New status
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO files (file_id, name, path, mime_type, size, modified_time, md5_checksum, status, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(file_id) DO UPDATE SET
                        name = excluded.name,
                        path = excluded.path,
                        mime_type = excluded.mime_type,
                        size = excluded.size,
                        modified_time = excluded.modified_time,
                        md5_checksum = excluded.md5_checksum,
                        status = excluded.status,
                        indexed_at = excluded.indexed_at
                    """,
                    (
                        file_metadata.file_id,
                        file_metadata.name,
                        file_metadata.path,
                        file_metadata.mime_type,
                        file_metadata.size,
                        file_metadata.modified_time.isoformat(),
                        file_metadata.md5_checksum,
                        status.value,
                        datetime.now().isoformat() if status == FileStatus.INDEXED else None
                    )
                )
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error updating file status: {e}", exc_info=True)
    
    def _get_indexed_files(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all indexed files from database.
        
        Returns:
            Dictionary mapping file_id to file info (md5_checksum, status)
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT file_id, md5_checksum, status FROM files")
                results = cursor.fetchall()
                
                return {
                    file_id: {"md5_checksum": md5, "status": status}
                    for file_id, md5, status in results
                }
                
        except Exception as e:
            logger.error(f"Error getting indexed files: {e}")
            return {}
    
    def _identify_changed_files(
        self,
        current_files: List[FileMetadata],
        indexed_files: Dict[str, Dict[str, Any]]
    ) -> List[FileMetadata]:
        """
        Identify files that are new or have been modified.
        
        Args:
            current_files: Current files from Google Drive
            indexed_files: Previously indexed files from database
            
        Returns:
            List of files that need to be processed
        """
        changed_files = []
        
        for file in current_files:
            if file.file_id not in indexed_files:
                # New file
                changed_files.append(file)
            else:
                indexed_info = indexed_files[file.file_id]
                # File modified or previously failed
                if (indexed_info["md5_checksum"] != file.md5_checksum or
                    indexed_info["status"] == FileStatus.FAILED.value):
                    changed_files.append(file)
        
        return changed_files
    
    def _identify_deleted_files(
        self,
        current_files: List[FileMetadata],
        indexed_files: Dict[str, Dict[str, Any]]
    ) -> Set[str]:
        """
        Identify files that have been deleted from Google Drive.
        
        Args:
            current_files: Current files from Google Drive
            indexed_files: Previously indexed files from database
            
        Returns:
            Set of file IDs that have been deleted
        """
        current_file_ids = {file.file_id for file in current_files}
        indexed_file_ids = set(indexed_files.keys())
        
        return indexed_file_ids - current_file_ids
    
    def _remove_file_from_index(self, file_id: str):
        """
        Remove a file from the index (mark as deleted).
        
        Args:
            file_id: File ID to remove
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE files SET status = ? WHERE file_id = ?",
                    (FileStatus.DELETED.value, file_id)
                )
                conn.commit()
                
            logger.info(f"Marked file as deleted: {file_id}")
            
        except Exception as e:
            logger.error(f"Error removing file from index: {e}")
    
    def _generate_report(self) -> IndexingReport:
        """
        Generate indexing report from current progress.
        
        Returns:
            IndexingReport with summary statistics
        """
        with self.progress_lock:
            # Count total sheets from database
            total_sheets = self._count_total_sheets()
            
            return IndexingReport(
                total_files=self.progress.total_files,
                total_sheets=total_sheets,
                files_processed=self.progress.files_processed,
                files_failed=self.progress.files_failed,
                files_skipped=self.progress.files_skipped,
                duration_seconds=self.progress.duration_seconds,
                errors=self.progress.errors.copy()
            )
    
    def _count_total_sheets(self) -> int:
        """
        Count total number of sheets in database.
        
        Returns:
            Total sheet count
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sheets")
                result = cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            logger.error(f"Error counting sheets: {e}")
            return 0

    # =========================================================================
    # Local File Indexing Methods (for file upload API)
    # =========================================================================
    
    def start_indexing(
        self,
        file_paths: List[str],
        incremental: bool = False
    ) -> str:
        """
        Start indexing for local files (uploaded via API).
        
        This method handles files uploaded directly to the server,
        as opposed to files from Google Drive.
        
        Args:
            file_paths: List of local file paths to index
            incremental: Whether to skip unchanged files (based on checksum)
            
        Returns:
            Job ID for tracking the indexing operation
        """
        import hashlib
        from pathlib import Path
        
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        
        logger.info(f"Starting local file indexing job {job_id} for {len(file_paths)} files")
        
        # Track job
        self._active_jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "file_paths": file_paths,
            "started_at": datetime.now(),
            "files_processed": 0,
            "files_failed": 0,
            "errors": []
        }
        
        # Process files in background thread
        import threading
        thread = threading.Thread(
            target=self._process_local_files,
            args=(job_id, file_paths, incremental)
        )
        thread.daemon = True
        thread.start()
        
        return job_id
    
    def _process_local_files(
        self,
        job_id: str,
        file_paths: List[str],
        incremental: bool
    ):
        """
        Process local files for indexing (runs in background thread).
        
        Args:
            job_id: Job identifier
            file_paths: List of file paths
            incremental: Whether to skip unchanged files
        """
        from pathlib import Path
        import hashlib
        from src.abstractions.embedding_service_factory import EmbeddingServiceFactory
        from src.abstractions.vector_store_factory import VectorStoreFactory
        from src.config import get_config
        from src.indexing.embedding_generator import EmbeddingGenerator
        from src.indexing.vector_storage import VectorStorageManager
        from src.indexing.metadata_storage import MetadataStorageManager
        
        try:
            # Initialize embedding and vector storage services
            config = get_config()
            embedding_service = EmbeddingServiceFactory.create(
                config.embedding.provider,
                config.embedding.config
            )
            vector_store = VectorStoreFactory.create(
                config.vector_store.provider,
                config.vector_store.config
            )
            
            embedding_generator = EmbeddingGenerator(
                embedding_service=embedding_service,
                batch_size=50
            )
            vector_storage = VectorStorageManager(vector_store=vector_store)
            metadata_storage = MetadataStorageManager(db_connection=self.db_connection)
            
            # Initialize vector store collections
            embedding_dimension = embedding_service.get_embedding_dimension()
            vector_storage.initialize_collections(embedding_dimension)
            
            for file_path in file_paths:
                path = Path(file_path)
                
                if not path.exists():
                    logger.warning(f"File not found: {file_path}")
                    self._active_jobs[job_id]["files_failed"] += 1
                    self._active_jobs[job_id]["errors"].append(f"File not found: {file_path}")
                    continue
                
                try:
                    # Read file content
                    with open(path, "rb") as f:
                        file_content = f.read()
                    
                    # Calculate MD5 checksum
                    md5_checksum = hashlib.md5(file_content).hexdigest()
                    
                    # Create file metadata
                    file_metadata = FileMetadata(
                        file_id=md5_checksum,  # Use checksum as ID for local files
                        name=path.name,
                        path=str(path),
                        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        size=len(file_content),
                        modified_time=datetime.fromtimestamp(path.stat().st_mtime),
                        md5_checksum=md5_checksum,
                        status=FileStatus.PENDING
                    )
                    
                    # Check if should skip (incremental mode)
                    if incremental and not self._should_index_file(file_metadata):
                        logger.info(f"Skipping unchanged file: {path.name}")
                        continue
                    
                    # Extract workbook data
                    workbook_data = self.content_extractor.extract_workbook_sync(
                        file_content=file_content,
                        file_name=path.name,
                        file_id=md5_checksum,
                        file_path=str(path),
                        modified_time=file_metadata.modified_time
                    )
                    
                    # Set file metadata in workbook data
                    workbook_data.file_id = md5_checksum
                    workbook_data.file_path = str(path)
                    
                    # Generate embeddings
                    logger.info(f"Generating embeddings for {path.name}")
                    embedding_result = embedding_generator.generate_workbook_embeddings(
                        workbook_data
                    )
                    
                    # Store embeddings in vector database
                    logger.info(f"Storing embeddings in vector store for {path.name}")
                    vector_storage.store_workbook_embeddings(
                        workbook_data=workbook_data,
                        embedding_result=embedding_result
                    )
                    
                    # Store metadata in SQLite
                    metadata_storage.store_workbook_metadata(workbook_data)
                    
                    # Update file status
                    self._update_file_status(file_metadata, FileStatus.INDEXED)
                    
                    self._active_jobs[job_id]["files_processed"] += 1
                    logger.info(f"Indexed file: {path.name} ({len(workbook_data.sheets)} sheets, {len(embedding_result.embeddings)} chunks)")
                    
                except Exception as e:
                    logger.error(f"Failed to index file {file_path}: {e}", exc_info=True)
                    self._active_jobs[job_id]["files_failed"] += 1
                    self._active_jobs[job_id]["errors"].append(f"{path.name}: {str(e)}")
            
            # Mark job as completed
            self._active_jobs[job_id]["status"] = "completed"
            self._active_jobs[job_id]["completed_at"] = datetime.now()
            
            # Move to completed jobs
            self._completed_jobs[job_id] = self._active_jobs.pop(job_id)
            
            logger.info(f"Indexing job {job_id} completed")
            
        except Exception as e:
            logger.error(f"Indexing job {job_id} failed: {e}", exc_info=True)
            self._active_jobs[job_id]["status"] = "failed"
            self._active_jobs[job_id]["errors"].append(str(e))
            
            # Move to failed jobs
            self._failed_jobs[job_id] = self._active_jobs.pop(job_id)
    
    def get_active_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of currently active indexing jobs.
        
        Returns:
            List of active job dictionaries
        """
        return list(self._active_jobs.values())
    
    def get_completed_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of completed indexing jobs.
        
        Returns:
            List of completed job dictionaries
        """
        return list(self._completed_jobs.values())
    
    def get_failed_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of failed indexing jobs.
        
        Returns:
            List of failed job dictionaries
        """
        return list(self._failed_jobs.values())
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific indexing job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status dictionary or None if not found
        """
        if job_id in self._active_jobs:
            return self._active_jobs[job_id]
        if job_id in self._completed_jobs:
            return self._completed_jobs[job_id]
        if job_id in self._failed_jobs:
            return self._failed_jobs[job_id]
        return None
