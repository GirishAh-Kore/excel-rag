"""
OpenAI Embedding Service Implementation

Supports OpenAI's text-embedding models with rate limiting and retry logic.
"""

from typing import List
import logging
import time
from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class OpenAIEmbeddingService(EmbeddingService):
    """OpenAI embedding implementation"""
    
    # Model dimensions mapping
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536
    }
    
    def __init__(self, api_key: str, model: str = "text-embedding-3-small", max_retries: int = 3):
        """
        Initialize OpenAI embedding service
        
        Args:
            api_key: OpenAI API key
            model: Model name (text-embedding-3-small or text-embedding-3-large)
            max_retries: Maximum number of retry attempts for API calls
        """
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
            self.model = model
            self.max_retries = max_retries
            
            if model not in self.MODEL_DIMENSIONS:
                logger.warning(f"Unknown model '{model}', defaulting dimension to 1536")
                self._dimension = 1536
            else:
                self._dimension = self.MODEL_DIMENSIONS[model]
            
            logger.info(f"OpenAI embedding service initialized with model: {model}")
        except ImportError:
            logger.error("openai package not installed. Install with: pip install openai")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI embedding service: {e}")
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
                response = self.client.embeddings.create(
                    input=texts,
                    model=self.model
                )
                embeddings = [item.embedding for item in response.data]
                logger.debug(f"Successfully embedded {len(texts)} texts")
                return embeddings
            
            except Exception as e:
                error_msg = str(e)
                
                # Check for rate limit errors
                if "rate_limit" in error_msg.lower() or "429" in error_msg:
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
