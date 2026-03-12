"""
Sentence Transformers Embedding Service Implementation

Local embedding generation using sentence-transformers library.
"""

from typing import List
import logging
from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class SentenceTransformerService(EmbeddingService):
    """Sentence Transformers (local) implementation"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize Sentence Transformers service
        
        Args:
            model_name: Model name from sentence-transformers library
                       Popular options:
                       - all-MiniLM-L6-v2 (384 dim, fast)
                       - all-mpnet-base-v2 (768 dim, better quality)
                       - multi-qa-MiniLM-L6-cos-v1 (384 dim, optimized for Q&A)
        """
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self.model_name = model_name
            self._dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"Sentence Transformers initialized with model: {model_name} (dimension: {self._dimension})")
        except ImportError:
            logger.error("sentence-transformers package not installed. Install with: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Sentence Transformers: {e}")
            raise
        
    def get_embedding_dimension(self) -> int:
        """Returns the dimension of embeddings"""
        return self._dimension
        
    def embed_text(self, text: str) -> List[float]:
        """Generates embedding for a single text"""
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            raise
        
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for multiple texts"""
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            logger.debug(f"Successfully embedded {len(texts)} texts")
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Failed to embed batch: {e}")
            raise
        
    def get_model_name(self) -> str:
        """Returns the model name"""
        return self.model_name
