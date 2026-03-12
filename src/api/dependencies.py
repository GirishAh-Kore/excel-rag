"""Dependency injection for API endpoints"""

import logging
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from src.config import get_config, AppConfig
from src.auth.authentication_service import AuthenticationService
from src.indexing.indexing_orchestrator import IndexingOrchestrator
from src.query.query_engine import QueryEngine
from src.abstractions.vector_store_factory import VectorStoreFactory
from src.abstractions.embedding_service_factory import EmbeddingServiceFactory
from src.abstractions.llm_service_factory import LLMServiceFactory
from src.abstractions.cache_service_factory import CacheServiceFactory
from src.indexing.metadata_storage import MetadataStorageManager
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


def get_vector_store(config: AppConfig = Depends(get_app_config)):
    """Get vector store instance"""
    return VectorStoreFactory.create(
        config.vector_store.provider,
        config.vector_store.config
    )


def get_embedding_service(config: AppConfig = Depends(get_app_config)):
    """Get embedding service instance"""
    return EmbeddingServiceFactory.create(
        config.embedding.provider,
        config.embedding.config
    )


def get_llm_service(config: AppConfig = Depends(get_app_config)):
    """Get LLM service instance (generation model)"""
    return LLMServiceFactory.create(
        config.llm.provider,
        config.llm.config
    )


def get_analysis_llm_service(config: AppConfig = Depends(get_app_config)):
    """Get LLM service configured for fast query analysis (gpt-4o-mini)"""
    analysis_config = dict(config.llm.config)
    analysis_config["model"] = config.query.analysis_model
    return LLMServiceFactory.create(config.llm.provider, analysis_config)


def get_generation_llm_service(config: AppConfig = Depends(get_app_config)):
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


def get_cache_service(config: AppConfig = Depends(get_app_config)):
    """Get cache service instance"""
    return CacheServiceFactory.create(
        config.cache.provider,
        config.cache.config
    )


def get_metadata_storage(config: AppConfig = Depends(get_app_config)) -> MetadataStorageManager:
    """Get metadata storage manager instance"""
    db_connection = DatabaseConnection(db_path=config.database.db_path)
    return MetadataStorageManager(db_connection=db_connection)


def get_conversation_manager(cache_service = Depends(get_cache_service)) -> ConversationManager:
    """Get conversation manager instance"""
    return ConversationManager(cache_service=cache_service)


def get_indexing_orchestrator(
    config: AppConfig = Depends(get_app_config),
    auth_service: AuthenticationService = Depends(get_auth_service)
) -> IndexingOrchestrator:
    """Get indexing orchestrator instance"""
    from src.gdrive.connector import GoogleDriveConnector
    from src.extraction.configurable_extractor import ConfigurableExtractor
    
    # Create Google Drive connector
    gdrive_connector = GoogleDriveConnector(auth_service=auth_service)
    
    # Create content extractor
    content_extractor = ConfigurableExtractor(config=config.extraction)
    
    # Create database connection
    db_connection = DatabaseConnection(db_path=config.database.db_path)
    
    return IndexingOrchestrator(
        gdrive_connector=gdrive_connector,
        content_extractor=content_extractor,
        db_connection=db_connection,
        max_workers=5
    )


def get_query_engine(
    config: AppConfig = Depends(get_app_config),
    auth_service: AuthenticationService = Depends(get_auth_service),
    vector_store = Depends(get_vector_store),
    embedding_service = Depends(get_embedding_service),
    llm_service = Depends(get_llm_service),
    cache_service = Depends(get_cache_service)
) -> QueryEngine:
    """Get query engine instance"""
    return QueryEngine(
        auth_service=auth_service,
        vector_store=vector_store,
        embedding_service=embedding_service,
        llm_service=llm_service,
        cache_service=cache_service,
        config=config
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
