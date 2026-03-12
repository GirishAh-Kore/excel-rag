"""
Dependency Injection Container for Excel Query Pipeline.

This module provides a centralized dependency injection container that wires
all components with proper dependency injection following SOLID principles.
All dependencies are created lazily and cached for reuse.

Key Features:
- Lazy initialization of services
- Thread-safe singleton pattern for shared services
- No module-level state - all state managed through container instance
- Follows DIP - depends on abstractions via factory patterns

Usage:
    container = Container.from_config(get_config())
    orchestrator = container.query_pipeline_orchestrator
    chunk_viewer = container.chunk_viewer

Requirements: All (SOLID compliance)
"""

import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from src.abstractions.cache_service import CacheService
from src.abstractions.cache_service_factory import CacheServiceFactory
from src.abstractions.embedding_service import EmbeddingService
from src.abstractions.embedding_service_factory import EmbeddingServiceFactory
from src.abstractions.llm_service import LLMService
from src.abstractions.llm_service_factory import LLMServiceFactory
from src.abstractions.vector_store import VectorStore
from src.abstractions.vector_store_factory import VectorStoreFactory
from src.config import AppConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceProvider:
    """
    Thread-safe lazy service provider with caching.
    
    Ensures services are created only once and reused across requests.
    """
    
    def __init__(self, factory: Callable[[], T]) -> None:
        """
        Initialize provider with factory function.
        
        Args:
            factory: Callable that creates the service instance.
        """
        self._factory = factory
        self._instance: Optional[T] = None
        self._lock = threading.Lock()
    
    def get(self) -> T:
        """
        Get or create the service instance.
        
        Returns:
            Service instance (cached after first creation).
        """
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    self._instance = self._factory()
        return self._instance
    
    def reset(self) -> None:
        """Reset the cached instance (useful for testing)."""
        with self._lock:
            self._instance = None



class Container:
    """
    Dependency Injection Container for the Excel Query Pipeline.
    
    Provides lazy-initialized, cached instances of all services following
    the Dependency Inversion Principle. Services are created on first access
    and reused for subsequent requests.
    
    All dependencies are wired through this container, ensuring:
    - No module-level state
    - All dependencies are injectable and testable
    - Services depend on abstractions, not concretions
    
    Example:
        >>> config = AppConfig.from_env()
        >>> container = Container.from_config(config)
        >>> orchestrator = container.query_pipeline_orchestrator
        >>> chunk_viewer = container.chunk_viewer
    """
    
    def __init__(self, config: AppConfig) -> None:
        """
        Initialize container with application configuration.
        
        Args:
            config: Application configuration instance.
        """
        self._config = config
        self._providers: dict[str, ServiceProvider] = {}
        self._lock = threading.Lock()
        
        logger.info("Container initialized with configuration")
    
    @classmethod
    def from_config(cls, config: AppConfig) -> "Container":
        """
        Create container from application configuration.
        
        Args:
            config: Application configuration.
            
        Returns:
            Configured Container instance.
        """
        return cls(config)
    
    def _get_or_create_provider(
        self,
        name: str,
        factory: Callable[[], T]
    ) -> ServiceProvider:
        """
        Get or create a service provider.
        
        Args:
            name: Unique name for the provider.
            factory: Factory function to create the service.
            
        Returns:
            ServiceProvider instance.
        """
        if name not in self._providers:
            with self._lock:
                if name not in self._providers:
                    self._providers[name] = ServiceProvider(factory)
        return self._providers[name]
    
    # =========================================================================
    # Core Infrastructure Services
    # =========================================================================
    
    @property
    def database_connection(self) -> "DatabaseConnection":
        """Get database connection instance."""
        from src.database.connection import DatabaseConnection
        
        provider = self._get_or_create_provider(
            "database_connection",
            lambda: DatabaseConnection(db_path=self._config.database.db_path)
        )
        return provider.get()
    
    @property
    def vector_store(self) -> VectorStore:
        """Get vector store instance."""
        provider = self._get_or_create_provider(
            "vector_store",
            lambda: VectorStoreFactory.create(
                self._config.vector_store.provider,
                self._config.vector_store.config
            )
        )
        return provider.get()
    
    @property
    def embedding_service(self) -> EmbeddingService:
        """Get embedding service instance."""
        provider = self._get_or_create_provider(
            "embedding_service",
            lambda: EmbeddingServiceFactory.create(
                self._config.embedding.provider,
                self._config.embedding.config
            )
        )
        return provider.get()
    
    @property
    def llm_service(self) -> LLMService:
        """Get LLM service instance."""
        provider = self._get_or_create_provider(
            "llm_service",
            lambda: LLMServiceFactory.create(
                self._config.llm.provider,
                self._config.llm.config
            )
        )
        return provider.get()
    
    @property
    def cache_service(self) -> CacheService:
        """Get cache service instance."""
        provider = self._get_or_create_provider(
            "cache_service",
            lambda: CacheServiceFactory.create(
                self._config.cache.backend,
                self._config.cache.config
            )
        )
        return provider.get()
    
    # =========================================================================
    # Chunk Viewer Components
    # =========================================================================
    
    @property
    def chunk_metadata_store(self) -> "ChunkMetadataStore":
        """Get chunk metadata store instance."""
        from src.chunk_viewer.metadata_store import ChunkMetadataStore
        
        provider = self._get_or_create_provider(
            "chunk_metadata_store",
            lambda: ChunkMetadataStore(db_connection=self.database_connection)
        )
        return provider.get()
    
    @property
    def chunk_version_store(self) -> "ChunkVersionStore":
        """Get chunk version store instance."""
        from src.chunk_viewer.version_store import ChunkVersionStore
        
        provider = self._get_or_create_provider(
            "chunk_version_store",
            lambda: ChunkVersionStore(db_connection=self.database_connection)
        )
        return provider.get()
    
    @property
    def feedback_store(self) -> "SQLiteFeedbackStore":
        """Get feedback store instance."""
        from src.chunk_viewer.feedback import SQLiteFeedbackStore
        
        provider = self._get_or_create_provider(
            "feedback_store",
            lambda: SQLiteFeedbackStore(db_connection=self.database_connection)
        )
        return provider.get()
    
    @property
    def feedback_collector(self) -> "FeedbackCollector":
        """Get feedback collector instance."""
        from src.chunk_viewer.feedback import FeedbackCollector
        
        provider = self._get_or_create_provider(
            "feedback_collector",
            lambda: FeedbackCollector(feedback_store=self.feedback_store)
        )
        return provider.get()
    
    @property
    def chunk_viewer(self) -> "ChunkViewer":
        """Get chunk viewer instance."""
        from src.chunk_viewer.viewer import ChunkViewer
        
        provider = self._get_or_create_provider(
            "chunk_viewer",
            lambda: ChunkViewer(
                metadata_store=self.chunk_metadata_store,
                version_store=self.chunk_version_store,
                vector_store=self.vector_store,
                embedding_service=self.embedding_service,
            )
        )
        return provider.get()

    
    # =========================================================================
    # Traceability Components
    # =========================================================================
    
    @property
    def trace_storage(self) -> "TraceStorage":
        """Get trace storage instance."""
        from src.traceability.trace_storage import TraceStorage
        
        provider = self._get_or_create_provider(
            "trace_storage",
            lambda: TraceStorage(db_connection=self.database_connection)
        )
        return provider.get()
    
    @property
    def trace_recorder(self) -> "TraceRecorder":
        """Get trace recorder instance."""
        from src.traceability.trace_recorder import TraceRecorder
        
        provider = self._get_or_create_provider(
            "trace_recorder",
            lambda: TraceRecorder(storage=self.trace_storage)
        )
        return provider.get()
    
    @property
    def lineage_storage(self) -> "LineageStorage":
        """Get lineage storage instance."""
        from src.traceability.lineage_storage import LineageStorage
        
        provider = self._get_or_create_provider(
            "lineage_storage",
            lambda: LineageStorage(db_connection=self.database_connection)
        )
        return provider.get()
    
    @property
    def lineage_tracker(self) -> "DataLineageTracker":
        """Get data lineage tracker instance."""
        from src.traceability.lineage_tracker import DataLineageTracker
        
        provider = self._get_or_create_provider(
            "lineage_tracker",
            lambda: DataLineageTracker(storage=self.lineage_storage)
        )
        return provider.get()
    
    # =========================================================================
    # Query Pipeline Components
    # =========================================================================
    
    @property
    def file_selector(self) -> "FileSelector":
        """Get file selector instance."""
        from src.query_pipeline.file_selector import FileSelector
        
        provider = self._get_or_create_provider(
            "file_selector",
            lambda: FileSelector(
                vector_store=self.vector_store,
                embedding_service=self.embedding_service,
                db_connection=self.database_connection,
            )
        )
        return provider.get()
    
    @property
    def sheet_selector(self) -> "SheetSelector":
        """Get sheet selector instance."""
        from src.query_pipeline.sheet_selector import SheetSelector
        
        provider = self._get_or_create_provider(
            "sheet_selector",
            lambda: SheetSelector(
                vector_store=self.vector_store,
                embedding_service=self.embedding_service,
            )
        )
        return provider.get()
    
    @property
    def query_classifier(self) -> "QueryClassifier":
        """Get query classifier instance."""
        from src.query_pipeline.classifier import QueryClassifier
        
        provider = self._get_or_create_provider(
            "query_classifier",
            lambda: QueryClassifier(
                llm_service=self.llm_service,
                embedding_service=self.embedding_service,
            )
        )
        return provider.get()
    
    @property
    def answer_generator(self) -> "AnswerGenerator":
        """Get answer generator instance."""
        from src.query_pipeline.answer_generator import AnswerGenerator
        
        provider = self._get_or_create_provider(
            "answer_generator",
            lambda: AnswerGenerator(llm_service=self.llm_service)
        )
        return provider.get()
    
    @property
    def data_retriever(self) -> "DataRetriever":
        """Get data retriever instance."""
        provider = self._get_or_create_provider(
            "data_retriever",
            lambda: DataRetriever(
                vector_store=self.vector_store,
                embedding_service=self.embedding_service,
            )
        )
        return provider.get()
    
    @property
    def query_pipeline_orchestrator(self) -> "QueryPipelineOrchestrator":
        """Get query pipeline orchestrator instance."""
        from src.query_pipeline.orchestrator import (
            QueryPipelineConfig,
            QueryPipelineOrchestrator,
        )
        
        provider = self._get_or_create_provider(
            "query_pipeline_orchestrator",
            lambda: QueryPipelineOrchestrator(
                file_selector=self.file_selector,
                sheet_selector=self.sheet_selector,
                query_classifier=self.query_classifier,
                answer_generator=self.answer_generator,
                trace_recorder=self.trace_recorder,
                data_retriever=self.data_retriever,
                session_store=self.cache_service,
                cache_service=self.cache_service,
                config=QueryPipelineConfig(),
            )
        )
        return provider.get()
    
    # =========================================================================
    # Batch and Template Components
    # =========================================================================
    
    @property
    def batch_store(self) -> "SQLiteBatchStore":
        """Get batch store instance."""
        from src.batch.store import SQLiteBatchStore
        
        provider = self._get_or_create_provider(
            "batch_store",
            lambda: SQLiteBatchStore(db_connection=self.database_connection)
        )
        return provider.get()
    
    @property
    def batch_processor(self) -> "BatchQueryProcessor":
        """Get batch query processor instance."""
        from src.batch.processor import BatchProcessorConfig, BatchQueryProcessor
        
        provider = self._get_or_create_provider(
            "batch_processor",
            lambda: BatchQueryProcessor(
                query_executor=self.query_pipeline_orchestrator,
                batch_store=self.batch_store,
                config=BatchProcessorConfig(),
            )
        )
        return provider.get()
    
    @property
    def template_store(self) -> "SQLiteTemplateStore":
        """Get template store instance."""
        from src.templates.store import SQLiteTemplateStore
        
        provider = self._get_or_create_provider(
            "template_store",
            lambda: SQLiteTemplateStore(db_connection=self.database_connection)
        )
        return provider.get()
    
    @property
    def template_manager(self) -> "TemplateManager":
        """Get template manager instance."""
        from src.templates.manager import TemplateManager
        
        provider = self._get_or_create_provider(
            "template_manager",
            lambda: TemplateManager(
                query_executor=self.query_pipeline_orchestrator,
                template_store=self.template_store,
            )
        )
        return provider.get()

    
    # =========================================================================
    # Access Control Components
    # =========================================================================
    
    @property
    def access_control_store(self) -> "AccessControlStore":
        """Get access control store instance."""
        from src.access_control.store import AccessControlStore
        
        provider = self._get_or_create_provider(
            "access_control_store",
            lambda: AccessControlStore(db_connection=self.database_connection)
        )
        return provider.get()
    
    @property
    def audit_logger(self) -> "AuditLogger":
        """Get audit logger instance."""
        from src.access_control.audit_logger import AuditLogger
        
        provider = self._get_or_create_provider(
            "audit_logger",
            lambda: AuditLogger(db_connection=self.database_connection)
        )
        return provider.get()
    
    @property
    def access_controller(self) -> "AccessController":
        """Get access controller instance."""
        from src.access_control.controller import AccessController
        
        provider = self._get_or_create_provider(
            "access_controller",
            lambda: AccessController(
                access_store=self.access_control_store,
                audit_logger=self.audit_logger,
            )
        )
        return provider.get()
    
    # =========================================================================
    # Cache Components
    # =========================================================================
    
    @property
    def query_cache(self) -> "QueryCache":
        """Get query cache instance."""
        from src.cache.query_cache import QueryCache
        
        provider = self._get_or_create_provider(
            "query_cache",
            lambda: QueryCache(
                cache_service=self.cache_service,
                db_connection=self.database_connection,
            )
        )
        return provider.get()
    
    @property
    def cache_invalidation_service(self) -> "CacheInvalidationService":
        """Get cache invalidation service instance."""
        from src.cache.invalidation_service import CacheInvalidationService
        
        provider = self._get_or_create_provider(
            "cache_invalidation_service",
            lambda: CacheInvalidationService(
                query_cache=self.query_cache,
                db_connection=self.database_connection,
            )
        )
        return provider.get()
    
    # =========================================================================
    # Webhook Components
    # =========================================================================
    
    @property
    def webhook_store(self) -> "WebhookStore":
        """Get webhook store instance."""
        from src.webhooks.store import WebhookStore
        
        provider = self._get_or_create_provider(
            "webhook_store",
            lambda: WebhookStore(db_connection=self.database_connection)
        )
        return provider.get()
    
    @property
    def webhook_manager(self) -> "WebhookManager":
        """Get webhook manager instance."""
        from src.webhooks.manager import WebhookManager
        
        provider = self._get_or_create_provider(
            "webhook_manager",
            lambda: WebhookManager(webhook_store=self.webhook_store)
        )
        return provider.get()
    
    # =========================================================================
    # Export Components
    # =========================================================================
    
    @property
    def export_store(self) -> "ExportStore":
        """Get export store instance."""
        from src.export.store import ExportStore
        
        provider = self._get_or_create_provider(
            "export_store",
            lambda: ExportStore(db_connection=self.database_connection)
        )
        return provider.get()
    
    @property
    def export_service(self) -> "ExportService":
        """Get export service instance."""
        from src.export.service import ExportService
        
        provider = self._get_or_create_provider(
            "export_service",
            lambda: ExportService(export_store=self.export_store)
        )
        return provider.get()
    
    # =========================================================================
    # Intelligence Components
    # =========================================================================
    
    @property
    def date_parser(self) -> "DateParser":
        """Get date parser instance."""
        from src.intelligence.date_parser import DateParser
        
        provider = self._get_or_create_provider(
            "date_parser",
            lambda: DateParser()
        )
        return provider.get()
    
    @property
    def unit_awareness_service(self) -> "UnitAwarenessService":
        """Get unit awareness service instance."""
        from src.intelligence.unit_awareness import UnitAwarenessService
        
        provider = self._get_or_create_provider(
            "unit_awareness_service",
            lambda: UnitAwarenessService()
        )
        return provider.get()
    
    @property
    def anomaly_detector(self) -> "AnomalyDetector":
        """Get anomaly detector instance."""
        from src.intelligence.anomaly_detector import AnomalyDetector
        
        provider = self._get_or_create_provider(
            "anomaly_detector",
            lambda: AnomalyDetector()
        )
        return provider.get()
    
    @property
    def relationship_detector(self) -> "RelationshipDetector":
        """Get relationship detector instance."""
        from src.intelligence.relationship_detector import RelationshipDetector
        
        provider = self._get_or_create_provider(
            "relationship_detector",
            lambda: RelationshipDetector(
                db_connection=self.database_connection,
                embedding_service=self.embedding_service,
            )
        )
        return provider.get()
    
    # =========================================================================
    # Extraction Components
    # =========================================================================
    
    @property
    def quality_scorer(self) -> "ExtractionQualityScorer":
        """Get extraction quality scorer instance."""
        from src.extraction.quality_scorer import ExtractionQualityScorer
        
        provider = self._get_or_create_provider(
            "quality_scorer",
            lambda: ExtractionQualityScorer()
        )
        return provider.get()
    
    @property
    def cost_estimator(self) -> "QueryCostEstimator":
        """Get query cost estimator instance."""
        from src.query_pipeline.cost_estimator import QueryCostEstimator
        
        provider = self._get_or_create_provider(
            "cost_estimator",
            lambda: QueryCostEstimator(db_connection=self.database_connection)
        )
        return provider.get()
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def reset_all(self) -> None:
        """
        Reset all cached service instances.
        
        Useful for testing or when configuration changes.
        """
        with self._lock:
            for provider in self._providers.values():
                provider.reset()
            self._providers.clear()
        logger.info("All container services reset")
    
    def reset_service(self, name: str) -> None:
        """
        Reset a specific service instance.
        
        Args:
            name: Name of the service to reset.
        """
        if name in self._providers:
            self._providers[name].reset()
            logger.info(f"Service '{name}' reset")



class DataRetriever:
    """
    Simple data retriever for query pipeline.
    
    Retrieves chunk data from vector store based on file and sheet selection.
    Implements the DataRetrieverProtocol expected by QueryPipelineOrchestrator.
    """
    
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
    ) -> None:
        """
        Initialize data retriever.
        
        Args:
            vector_store: Vector store for semantic search.
            embedding_service: Embedding service for query embedding.
        """
        self._vector_store = vector_store
        self._embedding_service = embedding_service
    
    def retrieve_data(
        self,
        file_id: str,
        sheet_names: list[str],
        query: str,
        max_chunks: int = 20
    ) -> "RetrievedData":
        """
        Retrieve data from vector store for query processing.
        
        Args:
            file_id: ID of the file to retrieve from.
            sheet_names: Names of sheets to retrieve from.
            query: Query for semantic search.
            max_chunks: Maximum chunks to retrieve.
            
        Returns:
            RetrievedData containing the retrieved chunks.
        """
        from src.query_pipeline.processors.base import RetrievedData
        
        # Generate query embedding
        query_embedding = self._embedding_service.embed_text(query)
        
        # Search vector store with file filter
        results = self._vector_store.search(
            query_embedding=query_embedding,
            top_k=max_chunks,
            filter_metadata={"file_id": file_id}
        )
        
        # Extract chunks and IDs from results
        chunks = []
        chunk_ids = []
        
        for result in results:
            if isinstance(result, dict):
                chunks.append(result.get("text", ""))
                chunk_ids.append(result.get("id", ""))
            else:
                # Handle tuple format (id, text, score)
                chunks.append(str(result))
                chunk_ids.append("")
        
        return RetrievedData(
            chunks=chunks,
            chunk_ids=chunk_ids,
            file_id=file_id,
            sheet_names=sheet_names,
        )


# =============================================================================
# Global Container Instance Management
# =============================================================================

_container_instance: Optional[Container] = None
_container_lock = threading.Lock()


def get_container() -> Container:
    """
    Get the global container instance.
    
    Creates the container on first access using the application configuration.
    
    Returns:
        Container instance.
        
    Raises:
        RuntimeError: If configuration is invalid.
    """
    global _container_instance
    
    if _container_instance is None:
        with _container_lock:
            if _container_instance is None:
                from src.config import get_config
                config = get_config()
                _container_instance = Container.from_config(config)
                logger.info("Global container instance created")
    
    return _container_instance


def reset_container() -> None:
    """
    Reset the global container instance.
    
    Useful for testing or when configuration changes.
    """
    global _container_instance
    
    with _container_lock:
        if _container_instance is not None:
            _container_instance.reset_all()
        _container_instance = None
        logger.info("Global container instance reset")


def set_container(container: Container) -> None:
    """
    Set a custom container instance (useful for testing).
    
    Args:
        container: Container instance to use.
    """
    global _container_instance
    
    with _container_lock:
        _container_instance = container
        logger.info("Custom container instance set")
