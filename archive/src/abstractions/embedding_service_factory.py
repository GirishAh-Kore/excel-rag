"""
Embedding Service Factory

Factory for creating embedding service instances based on configuration.
"""

from typing import Dict, Any
import logging
from .embedding_service import EmbeddingService
from .openai_embedding_service import OpenAIEmbeddingService
from .sentence_transformer_service import SentenceTransformerService
from .cohere_embedding_service import CohereEmbeddingService

logger = logging.getLogger(__name__)


class EmbeddingServiceFactory:
    """Factory for creating embedding service instances"""
    
    @staticmethod
    def create(provider: str, config: Dict[str, Any]) -> EmbeddingService:
        """
        Creates an embedding service instance based on provider
        
        Args:
            provider: Provider name ("openai", "sentence-transformers", "cohere")
            config: Configuration dictionary for the provider
            
        Returns:
            EmbeddingService instance
            
        Raises:
            ValueError: If provider is unknown or config is invalid
        """
        provider = provider.lower()
        
        try:
            if provider == "openai":
                api_key = config.get("api_key")
                if not api_key:
                    raise ValueError("OpenAI requires 'api_key' in config")
                
                model = config.get("model", "text-embedding-3-small")
                max_retries = config.get("max_retries", 3)
                
                logger.info(f"Creating OpenAI embedding service with model: {model}")
                return OpenAIEmbeddingService(
                    api_key=api_key,
                    model=model,
                    max_retries=max_retries
                )
            
            elif provider == "sentence-transformers":
                model = config.get("model", "all-MiniLM-L6-v2")
                
                logger.info(f"Creating Sentence Transformers service with model: {model}")
                return SentenceTransformerService(model_name=model)
            
            elif provider == "cohere":
                api_key = config.get("api_key")
                if not api_key:
                    raise ValueError("Cohere requires 'api_key' in config")
                
                model = config.get("model", "embed-english-v3.0")
                max_retries = config.get("max_retries", 3)
                
                logger.info(f"Creating Cohere embedding service with model: {model}")
                return CohereEmbeddingService(
                    api_key=api_key,
                    model=model,
                    max_retries=max_retries
                )
            
            else:
                raise ValueError(
                    f"Unknown embedding provider: {provider}. "
                    f"Supported providers: 'openai', 'sentence-transformers', 'cohere'"
                )
        
        except Exception as e:
            logger.error(f"Failed to create embedding service for provider '{provider}': {e}")
            raise
