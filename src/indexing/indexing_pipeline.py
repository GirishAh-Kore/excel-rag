"""
Indexing Pipeline

This module provides a high-level interface for the complete indexing pipeline,
integrating the orchestrator, embedding generator, vector storage, and metadata storage.
It also provides progress tracking and reporting capabilities.
"""

import logging
import time
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from src.abstractions.cache_service import CacheService
from src.abstractions.embedding_service import EmbeddingService
from src.abstractions.vector_store import VectorStore
from src.database.connection import DatabaseConnection
from src.extraction.configurable_extractor import ConfigurableExtractor
from src.gdrive.connector import GoogleDriveConnector
from src.indexing.embedding_generator import EmbeddingGenerator
from src.indexing.indexing_orchestrator import IndexingOrchestrator, IndexingProgress
from src.indexing.metadata_storage import MetadataStorageManager
from src.indexing.vector_storage import VectorStorageManager
from src.models.domain_models import IndexingReport, WorkbookData


logger = logging.getLogger(__name__)


# =============================================================================
# Protocols
# =============================================================================


@runtime_checkable
class IndexingEventListenerProtocol(Protocol):
    """
    Protocol for indexing event listeners.
    
    Implementations receive notifications when indexing events occur.
    Used for cache invalidation and other side effects.
    """
    
    def on_file_indexed(self, file_id: str, file_name: str) -> None:
        """Called when a file is successfully indexed or re-indexed."""
        ...
    
    def on_file_removed(self, file_id: str) -> None:
        """Called when a file is removed from the index."""
        ...


class IndexingPipeline:
    """
    High-level indexing pipeline that coordinates all indexing components.
    
    This class provides a simple interface for:
    - Full indexing of all files
    - Incremental indexing of changed files
    - Progress tracking and reporting
    - Cost estimation for API-based services
    
    Note: Currently uses synchronous extraction (extract_workbook_sync) which does
    not include LLM-generated sheet summaries. An async version will be added in
    the future to support full ConfigurableExtractor capabilities including LLM
    summarization, smart extraction, and advanced extraction strategies.
    """
    
    def __init__(
        self,
        gdrive_connector: GoogleDriveConnector,
        content_extractor: ConfigurableExtractor,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        db_connection: DatabaseConnection,
        cache_service: Optional[CacheService] = None,
        event_listener: Optional[IndexingEventListenerProtocol] = None,
        max_workers: int = 5,
        batch_size: int = 100,
        cost_per_token: float = 0.0
    ):
        """
        Initialize the indexing pipeline.
        
        Args:
            gdrive_connector: Google Drive connector
            content_extractor: Content extractor
            embedding_service: Embedding service
            vector_store: Vector store
            db_connection: Database connection
            cache_service: Optional cache service
            event_listener: Optional listener for indexing events (e.g., cache invalidation)
            max_workers: Maximum concurrent workers
            batch_size: Embedding batch size
            cost_per_token: Cost per token for embeddings (USD)
        """
        self.gdrive_connector = gdrive_connector
        self.content_extractor = content_extractor
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.db_connection = db_connection
        
        # Initialize components
        self.embedding_generator = EmbeddingGenerator(
            embedding_service=embedding_service,
            cache_service=cache_service,
            batch_size=batch_size,
            cost_per_token=cost_per_token
        )
        
        self.vector_storage = VectorStorageManager(vector_store=vector_store)
        self.metadata_storage = MetadataStorageManager(db_connection=db_connection)
        
        # Create custom orchestrator that uses our pipeline
        self.orchestrator = EnhancedIndexingOrchestrator(
            gdrive_connector=gdrive_connector,
            content_extractor=content_extractor,
            db_connection=db_connection,
            embedding_generator=self.embedding_generator,
            vector_storage=self.vector_storage,
            metadata_storage=self.metadata_storage,
            event_listener=event_listener,
            max_workers=max_workers
        )
        
        # Initialize vector store collections
        embedding_dimension = embedding_service.get_embedding_dimension()
        self.vector_storage.initialize_collections(embedding_dimension)
        
        logger.info(
            f"IndexingPipeline initialized: "
            f"embedding_dim={embedding_dimension}, "
            f"max_workers={max_workers}, "
            f"batch_size={batch_size}"
        )
    
    def full_index(self) -> IndexingReport:
        """
        Perform full indexing of all files.
        
        Returns:
            IndexingReport with summary and cost information
        """
        logger.info("Starting full indexing pipeline")
        start_time = time.time()
        
        try:
            report = self.orchestrator.full_index()
            
            # Add cost information
            cost_summary = self.embedding_generator.get_cost_summary()
            logger.info(f"Indexing cost summary: {cost_summary}")
            
            elapsed = time.time() - start_time
            logger.info(f"Full indexing completed in {elapsed:.2f} seconds")
            
            return report
            
        except Exception as e:
            logger.error(f"Full indexing failed: {e}", exc_info=True)
            raise
    
    def incremental_index(self) -> IndexingReport:
        """
        Perform incremental indexing of changed files.
        
        Returns:
            IndexingReport with summary and cost information
        """
        logger.info("Starting incremental indexing pipeline")
        start_time = time.time()
        
        try:
            report = self.orchestrator.incremental_index()
            
            # Add cost information
            cost_summary = self.embedding_generator.get_cost_summary()
            logger.info(f"Indexing cost summary: {cost_summary}")
            
            elapsed = time.time() - start_time
            logger.info(f"Incremental indexing completed in {elapsed:.2f} seconds")
            
            return report
            
        except Exception as e:
            logger.error(f"Incremental indexing failed: {e}", exc_info=True)
            raise
    
    def index_file(self, file_id: str, force: bool = False) -> bool:
        """
        Index a specific file.
        
        Args:
            file_id: File ID to index
            force: Force reindexing
            
        Returns:
            True if successful
        """
        return self.orchestrator.index_file(file_id, force)
    
    def get_progress(self) -> IndexingProgress:
        """Get current indexing progress"""
        return self.orchestrator.get_progress()
    
    def pause(self):
        """Pause indexing"""
        self.orchestrator.pause()
    
    def resume(self):
        """Resume indexing"""
        self.orchestrator.resume()
    
    def stop(self):
        """Stop indexing"""
        self.orchestrator.stop()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive indexing statistics.
        
        Returns:
            Dictionary with statistics from all components
        """
        metadata_stats = self.metadata_storage.get_indexing_statistics()
        vector_stats = self.vector_storage.get_collection_stats()
        cost_summary = self.embedding_generator.get_cost_summary()
        progress = self.get_progress()
        
        return {
            "metadata": metadata_stats,
            "vector_store": vector_stats,
            "embedding_cost": cost_summary,
            "current_progress": {
                "state": progress.state.value,
                "progress_percentage": progress.progress_percentage,
                "files_processed": progress.files_processed,
                "files_failed": progress.files_failed,
                "files_skipped": progress.files_skipped,
                "duration_seconds": progress.duration_seconds
            }
        }


class EnhancedIndexingOrchestrator(IndexingOrchestrator):
    """
    Enhanced orchestrator that integrates embedding generation and storage.
    
    This extends the base IndexingOrchestrator to include the full pipeline:
    download → extract → embed → store in vector DB → store metadata
    
    Also supports event listeners for cache invalidation on re-indexing.
    """
    
    def __init__(
        self,
        gdrive_connector: GoogleDriveConnector,
        content_extractor: ConfigurableExtractor,
        db_connection: DatabaseConnection,
        embedding_generator: EmbeddingGenerator,
        vector_storage: VectorStorageManager,
        metadata_storage: MetadataStorageManager,
        event_listener: Optional[IndexingEventListenerProtocol] = None,
        max_workers: int = 5
    ):
        """
        Initialize enhanced orchestrator.
        
        Args:
            gdrive_connector: Google Drive connector
            content_extractor: Content extractor
            db_connection: Database connection
            embedding_generator: Embedding generator
            vector_storage: Vector storage manager
            metadata_storage: Metadata storage manager
            event_listener: Optional listener for indexing events (cache invalidation)
            max_workers: Maximum concurrent workers
        """
        super().__init__(
            gdrive_connector=gdrive_connector,
            content_extractor=content_extractor,
            db_connection=db_connection,
            max_workers=max_workers
        )
        
        self.embedding_generator = embedding_generator
        self.vector_storage = vector_storage
        self.metadata_storage = metadata_storage
        self._event_listener = event_listener
    
    def _process_single_file(self, file_metadata) -> bool:
        """
        Process a single file through the complete pipeline.
        
        Args:
            file_metadata: File metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update current file
            with self.progress_lock:
                self.progress.current_file = file_metadata.name
            
            logger.info(f"Processing file: {file_metadata.name}")
            
            # Mark file as pending
            from src.models.domain_models import FileStatus
            self.metadata_storage.update_file_status(
                file_metadata.file_id,
                FileStatus.PENDING
            )
            
            # Download file content
            file_content = self.gdrive_connector.download_file(file_metadata.file_id)
            
            # Extract workbook data (using synchronous method)
            # Note: LLM summarization is not used in sync mode
            # For LLM summaries, use async indexing pipeline (future enhancement)
            workbook_data = self.content_extractor.extract_workbook_sync(
                file_content=file_content,
                file_name=file_metadata.name,
                file_id=file_metadata.file_id,
                file_path=file_metadata.path,
                modified_time=file_metadata.modified_time
            )
            
            # Set file metadata in workbook data
            workbook_data.file_id = file_metadata.file_id
            workbook_data.file_path = file_metadata.path
            workbook_data.modified_time = file_metadata.modified_time
            
            # Generate embeddings
            embedding_result = self.embedding_generator.generate_workbook_embeddings(
                workbook_data
            )
            
            # Store embeddings in vector database
            self.vector_storage.store_workbook_embeddings(
                workbook_data=workbook_data,
                embedding_result=embedding_result
            )
            
            # Store metadata in SQLite
            self.metadata_storage.store_workbook_metadata(workbook_data)
            
            # Update file status to indexed
            self.metadata_storage.update_file_status(
                file_metadata.file_id,
                FileStatus.INDEXED
            )
            
            # Notify event listener for cache invalidation (Requirement 43.2)
            if self._event_listener is not None:
                try:
                    self._event_listener.on_file_indexed(
                        file_id=file_metadata.file_id,
                        file_name=file_metadata.name
                    )
                except Exception as listener_error:
                    logger.warning(
                        f"Event listener error for file {file_metadata.name}: "
                        f"{listener_error}"
                    )
            
            # Update progress
            with self.progress_lock:
                self.progress.files_processed += 1
            
            logger.info(
                f"Successfully processed file: {file_metadata.name} "
                f"({len(workbook_data.sheets)} sheets, "
                f"{len(embedding_result.embeddings)} embeddings, "
                f"{sum(embedding_result.from_cache)} from cache)"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process file {file_metadata.name}: {e}", exc_info=True)
            
            # Mark file as failed
            self.metadata_storage.update_file_status(
                file_metadata.file_id,
                FileStatus.FAILED
            )
            
            # Update progress
            with self.progress_lock:
                self.progress.files_failed += 1
                self.progress.errors.append(f"{file_metadata.name}: {str(e)}")
            
            return False
    
    def _remove_file_from_index(self, file_id: str) -> None:
        """
        Remove a file from both vector store and metadata database.
        
        Args:
            file_id: File ID to remove
        """
        try:
            # Remove from vector store
            self.vector_storage.remove_file_embeddings(file_id)
            
            # Mark as deleted in metadata database
            self.metadata_storage.update_file_status(file_id, FileStatus.DELETED)
            
            # Notify event listener for cache invalidation (Requirement 43.2)
            if self._event_listener is not None:
                try:
                    self._event_listener.on_file_removed(file_id=file_id)
                except Exception as listener_error:
                    logger.warning(
                        f"Event listener error for removed file {file_id}: "
                        f"{listener_error}"
                    )
            
            logger.info(f"Removed file from index: {file_id}")
            
        except Exception as e:
            logger.error(f"Error removing file from index: {e}")
