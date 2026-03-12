"""
Embedding Service Factory

Factory for creating embedding service instances based on configuration.
"""

from typing import Dict, Any
import logging
from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class EmbeddingServiceFactory:
    """Factory for creating embedding service instances"""
    
    @staticmethod
    def create(provider: str, config: Dict[str, Any]) -> EmbeddingService:
        """
        Creates an embedding service instance based on provider
        
        Args:
            provider: Provider name ("openai", "sentence-transformers", "cohere", "bge", "bge-m3")
            config: Configuration dictionary for the provider
            
        Returns:
            EmbeddingService instance
            
        Raises:
            ValueError: If provider is unknown or config is invalid
        """
        provider = provider.lower()
        
        try:
            if provider == "openai":
                from .openai_embedding_service import OpenAIEmbeddingService
                
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
                from .sentence_transformer_service import SentenceTransformerService
                
                model = config.get("model", "all-MiniLM-L6-v2")
                
                logger.info(f"Creating Sentence Transformers service with model: {model}")
                return SentenceTransformerService(model_name=model)
            
            elif provider == "cohere":
                from .cohere_embedding_service import CohereEmbeddingService
                
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
            
            elif provider in ("bge", "bge-m3", "bge-large"):
                from .bge_embedding_service import BGEEmbeddingService
                
                model = config.get("model", "BAAI/bge-m3")
                use_fp16 = config.get("use_fp16", True)
                device = config.get("device")  # None = auto-detect
                max_length = config.get("max_length", 8192)
                
                logger.info(f"Creating BGE embedding service with model: {model}")
                return BGEEmbeddingService(
                    model_name=model,
                    use_fp16=use_fp16,
                    device=device,
                    max_length=max_length
                )
            
            else:
                raise ValueError(
                    f"Unknown embedding provider: {provider}. "
                    f"Supported providers: 'openai', 'sentence-transformers', 'cohere', 'bge', 'bge-m3'"
                )
        
        except Exception as e:
            logger.error(f"Failed to create embedding service for provider '{provider}': {e}")
            raise
