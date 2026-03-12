"""
Embedding Service Abstraction Layer

Provides a pluggable interface for embedding model providers,
supporting OpenAI, Sentence Transformers, Cohere, and others.
"""

from abc import ABC, abstractmethod
from typing import List
import logging

logger = logging.getLogger(__name__)


class EmbeddingService(ABC):
    """Abstract base class for embedding model providers"""
    
    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """
        Returns the dimension of embeddings produced by this model
        
        Returns:
            Embedding dimension (e.g., 384, 1536, 3072)
        """
        pass
        
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """
        Generates embedding for a single text
        
        Args:
            text: Input text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        pass
        
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embeddings for multiple texts (batched for efficiency)
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of embedding vectors
        """
        pass
        
    @abstractmethod
    def get_model_name(self) -> str:
        """
        Returns the name/identifier of the embedding model
        
        Returns:
            Model name string
        """
        pass
