"""Dependency injection for API endpoints"""

import logging
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from src.config import get_config, AppConfig
from src.auth.authentication_service import AuthenticationService
from src.indexing.indexing_orchestrator import IndexingOrchestrator
from src.query.query_engine import QueryEngine
from src.abstractions.vector_store import VectorStore
from src.abstractions.vector_store_factory import VectorStoreFactory
from src.abstractions.embedding_service import EmbeddingService
from src.abstractions.embedding_service_factory import EmbeddingServiceFactory
from src.abstractions.llm_service import LLMService
from src.abstractions.llm_service_factory import LLMServiceFactory
from src.abstractions.cache_service import CacheService
from src.abstractions.cache_service_factory import CacheServiceFactory
from src.indexing.metadata_storage import MetadataStorageManager
from src.indexing.vector_storage import VectorStorageManager
from src.query.conversation_manager import ConversationManager
from src.query.reranker import ResultReranker
from src.query.hybrid_searcher import HybridSearcher
from src.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration Dependencies
# ============================================================================

def get_app_config() -> AppConfig:
    """Get application configuration"""
    return get_config()


# ============================================================================
# Service Dependencies
# ============================================================================

def get_auth_service(config: AppConfig = Depends(get_app_config)) -> AuthenticationService:
    """Get authentication service instance"""
    return AuthenticationService(config=config.google_drive)


def get_vector_store(config: AppConfig = Depends(get_app_config)) -> VectorStore:
    """Get vector store instance"""
    return VectorStoreFactory.create(
        config.vector_store.provider,
        config.vector_store.config
    )


def get_embedding_service(config: AppConfig = Depends(get_app_config)) -> EmbeddingService:
    """Get embedding service instance"""
    return EmbeddingServiceFactory.create(
        config.embedding.provider,
        config.embedding.config
    )


def get_llm_service(config: AppConfig = Depends(get_app_config)) -> LLMService:
    """Get LLM service instance (generation model)"""
    return LLMServiceFactory.create(
        config.llm.provider,
        config.llm.config
    )


def get_analysis_llm_service(config: AppConfig = Depends(get_app_config)) -> LLMService:
    """Get LLM service configured for fast query analysis (gpt-4o-mini)"""
    analysis_config = dict(config.llm.config)
    analysis_config["model"] = config.query.analysis_model
    return LLMServiceFactory.create(config.llm.provider, analysis_config)


def get_generation_llm_service(config: AppConfig = Depends(get_app_config)) -> LLMService:
    """Get LLM service configured for high-quality answer generation (gpt-4o)"""
    generation_config = dict(config.llm.config)
    generation_config["model"] = config.query.generation_model
    return LLMServiceFactory.create(config.llm.provider, generation_config)


def get_reranker(config: AppConfig = Depends(get_app_config)) -> Optional[ResultReranker]:
    """Get cross-encoder reranker (None if disabled)"""
    if not config.query.enable_reranking:
        return None
    return ResultReranker(model_name=config.query.reranker_model)


def get_hybrid_searcher(config: AppConfig = Depends(get_app_config)) -> Optional[HybridSearcher]:
    """Get hybrid searcher (None if disabled)"""
    if not config.query.enable_hybrid_search:
        return None
    return HybridSearcher()


def get_cache_service(config: AppConfig = Depends(get_app_config)) -> CacheService:
    """Get cache service instance"""
    return CacheServiceFactory.create(
        config.cache.backend,
        config.cache.config
    )


def get_metadata_storage(config: AppConfig = Depends(get_app_config)) -> MetadataStorageManager:
    """Get metadata storage manager instance"""
    db_connection = DatabaseConnection(db_path=config.database.db_path)
    return MetadataStorageManager(db_connection=db_connection)


def get_conversation_manager(
    cache_service: CacheService = Depends(get_cache_service),
    config: AppConfig = Depends(get_app_config)
) -> ConversationManager:
    """Get conversation manager instance"""
    return ConversationManager(
        cache_service=cache_service,
        config=config.conversation
    )


def get_indexing_orchestrator(
    config: AppConfig = Depends(get_app_config),
    auth_service: AuthenticationService = Depends(get_auth_service)
) -> IndexingOrchestrator:
    """Get indexing orchestrator instance"""
    from src.gdrive.connector import GoogleDriveConnector
    from src.extraction.configurable_extractor import ConfigurableExtractor
    from src.extraction.extraction_strategy import ExtractionConfig
    
    # Create Google Drive connector
    gdrive_connector = GoogleDriveConnector(auth_service=auth_service)
    
    # Convert ExtractionSettings (dataclass) to ExtractionConfig (Pydantic)
    # This allows the Pydantic model to handle validation
    extraction_config = ExtractionConfig(
        default_strategy=config.extraction.default_strategy,
        max_rows_per_sheet=config.extraction.max_rows_per_sheet,
        max_file_size_mb=config.extraction.max_file_size_mb,
        enable_llm_summarization=config.extraction.enable_llm_summarization,
        summarization_provider=config.extraction.summarization_provider,
        summarization_model=config.extraction.summarization_model,
        summarization_max_tokens=config.extraction.summarization_max_tokens,
        enable_gemini=config.extraction.enable_gemini,
        gemini_api_key=config.extraction.gemini_api_key,
        gemini_model=config.extraction.gemini_model,
        gemini_fallback_on_error=config.extraction.gemini_fallback_on_error,
        enable_llamaparse=config.extraction.enable_llamaparse,
        llamaparse_api_key=config.extraction.llamaparse_api_key,
        enable_docling=config.extraction.enable_docling,
        docling_model=config.extraction.docling_model,
        enable_unstructured=config.extraction.enable_unstructured,
        unstructured_api_key=config.extraction.unstructured_api_key,
        unstructured_api_url=config.extraction.unstructured_api_url,
        unstructured_strategy=config.extraction.unstructured_strategy,
        use_auto_strategy=config.extraction.use_auto_strategy,
        complexity_threshold=config.extraction.complexity_threshold
    )
    
    # Create content extractor with Pydantic config
    content_extractor = ConfigurableExtractor(config=extraction_config)
    
    # Create database connection
    db_connection = DatabaseConnection(db_path=config.database.db_path)
    
    return IndexingOrchestrator(
        gdrive_connector=gdrive_connector,
        content_extractor=content_extractor,
        db_connection=db_connection,
        max_workers=5
    )


def get_vector_storage_manager(
    vector_store: VectorStore = Depends(get_vector_store)
) -> VectorStorageManager:
    """Get vector storage manager instance"""
    return VectorStorageManager(vector_store=vector_store)


def get_query_engine(
    vector_storage: VectorStorageManager = Depends(get_vector_storage_manager),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    llm_service: LLMService = Depends(get_llm_service),
    cache_service: CacheService = Depends(get_cache_service),
    conversation_manager: ConversationManager = Depends(get_conversation_manager)
) -> QueryEngine:
    """Get query engine instance"""
    return QueryEngine(
        llm_service=llm_service,
        embedding_service=embedding_service,
        cache_service=cache_service,
        vector_storage=vector_storage,
        conversation_manager=conversation_manager
    )


# ============================================================================
# Authentication Dependencies
# ============================================================================

async def require_authentication(
    auth_service: AuthenticationService = Depends(get_auth_service)
) -> AuthenticationService:
    """Require valid authentication for endpoint access"""
    if not auth_service.is_authenticated():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please authenticate first.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return auth_service


# ============================================================================
# Correlation ID Dependencies
# ============================================================================

async def get_correlation_id(
    x_correlation_id: Optional[str] = Header(None)
) -> str:
    """Get or generate correlation ID for request tracing"""
    import uuid
    return x_correlation_id or str(uuid.uuid4())
