"""
Cohere Embedding Service Implementation

Supports Cohere's embedding models with rate limiting and retry logic.
"""

from typing import List
import logging
import time
from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class CohereEmbeddingService(EmbeddingService):
    """Cohere embedding implementation"""
    
    # Model dimensions mapping
    MODEL_DIMENSIONS = {
        "embed-english-v3.0": 1024,
        "embed-english-light-v3.0": 384,
        "embed-multilingual-v3.0": 1024,
        "embed-english-v2.0": 4096
    }
    
    def __init__(self, api_key: str, model: str = "embed-english-v3.0", max_retries: int = 3):
        """
        Initialize Cohere embedding service
        
        Args:
            api_key: Cohere API key
            model: Model name (embed-english-v3.0, embed-english-light-v3.0, etc.)
            max_retries: Maximum number of retry attempts for API calls
        """
        try:
            import cohere
            self.client = cohere.Client(api_key)
            self.model = model
            self.max_retries = max_retries
            
            if model not in self.MODEL_DIMENSIONS:
                logger.warning(f"Unknown model '{model}', defaulting dimension to 1024")
                self._dimension = 1024
            else:
                self._dimension = self.MODEL_DIMENSIONS[model]
            
            logger.info(f"Cohere embedding service initialized with model: {model}")
        except ImportError:
            logger.error("cohere package not installed. Install with: pip install cohere")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Cohere embedding service: {e}")
            raise
        
    def get_embedding_dimension(self) -> int:
        """Returns the dimension of embeddings"""
        return self._dimension
        
    def embed_text(self, text: str) -> List[float]:
        """Generates embedding for a single text"""
        return self._embed_with_retry([text])[0]
        
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for multiple texts"""
        return self._embed_with_retry(texts)
        
    def get_model_name(self) -> str:
        """Returns the model name"""
        return self.model
    
    def _embed_with_retry(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds texts with retry logic for rate limiting
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        for attempt in range(self.max_retries):
            try:
                response = self.client.embed(
                    texts=texts,
                    model=self.model,
                    input_type="search_document"  # For indexing documents
                )
                embeddings = response.embeddings
                logger.debug(f"Successfully embedded {len(texts)} texts")
                return embeddings
            
            except Exception as e:
                error_msg = str(e)
                
                # Check for rate limit errors
                if "rate_limit" in error_msg.lower() or "429" in error_msg or "too_many_requests" in error_msg.lower():
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(f"Rate limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                    continue
                
                # Check for timeout or network errors
                elif "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                    wait_time = 2 ** attempt
                    logger.warning(f"Network error, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                    continue
                
                # Other errors - don't retry
                else:
                    logger.error(f"Failed to generate embeddings: {e}")
                    raise
        
        # Max retries exceeded
        raise Exception(f"Failed to generate embeddings after {self.max_retries} attempts")
