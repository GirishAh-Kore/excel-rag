"""Pytest configuration and fixtures for integration tests"""

import pytest
import os
from unittest.mock import Mock, patch

# Set test environment variables before any imports
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
os.environ["DATABASE_PATH"] = ":memory:"


@pytest.fixture(scope="session", autouse=True)
def mock_heavy_dependencies():
    """Mock heavy dependencies for all tests"""
    
    # Mock vector store to avoid initialization
    with patch('src.abstractions.vector_store_factory.VectorStoreFactory.create') as mock_vector:
        mock_vector.return_value = Mock()
        
        # Mock embedding service
        with patch('src.abstractions.embedding_service_factory.EmbeddingServiceFactory.create') as mock_embed:
            mock_embed.return_value = Mock()
            
            # Mock LLM service
            with patch('src.abstractions.llm_service_factory.LLMServiceFactory.create') as mock_llm:
                mock_llm.return_value = Mock()
                
                # Mock cache service
                with patch('src.abstractions.cache_service_factory.CacheServiceFactory.create') as mock_cache:
                    mock_cache.return_value = Mock()
                    
                    yield {
                        'vector_store': mock_vector,
                        'embedding_service': mock_embed,
                        'llm_service': mock_llm,
                        'cache_service': mock_cache
                    }
