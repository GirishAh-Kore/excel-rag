"""
Vector Store Abstraction Layer

Provides a pluggable interface for vector database implementations,
allowing easy switching between ChromaDB (MVP) and OpenSearch (production).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """Abstract base class for vector database implementations"""
    
    @abstractmethod
    def create_collection(self, name: str, dimension: int, metadata_schema: Dict[str, Any]) -> bool:
        """
        Creates a new collection for storing embeddings
        
        Args:
            name: Collection name
            dimension: Embedding vector dimension
            metadata_schema: Schema definition for metadata fields
            
        Returns:
            True if successful, False otherwise
        """
        pass
        
    @abstractmethod
    def add_embeddings(
        self, 
        collection: str,
        ids: List[str], 
        embeddings: List[List[float]], 
        documents: List[str],
        metadata: List[Dict[str, Any]]
    ) -> bool:
        """
        Adds embeddings to a collection
        
        Args:
            collection: Collection name
            ids: Unique identifiers for each embedding
            embeddings: List of embedding vectors
            documents: Original text documents
            metadata: Metadata for each embedding
            
        Returns:
            True if successful, False otherwise
        """
        pass
        
    @abstractmethod
    def search(
        self,
        collection: str,
        query_embedding: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Searches for similar embeddings
        
        Args:
            collection: Collection name
            query_embedding: Query vector
            top_k: Number of results to return
            filters: Optional metadata filters
            
        Returns:
            List of results with id, score, document, and metadata
        """
        pass
        
    @abstractmethod
    def delete_by_id(self, collection: str, ids: List[str]) -> bool:
        """
        Deletes embeddings by ID
        
        Args:
            collection: Collection name
            ids: List of IDs to delete
            
        Returns:
            True if successful, False otherwise
        """
        pass
        
    @abstractmethod
    def update_embeddings(
        self,
        collection: str,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadata: List[Dict[str, Any]]
    ) -> bool:
        """
        Updates existing embeddings
        
        Args:
            collection: Collection name
            ids: IDs to update
            embeddings: New embedding vectors
            documents: New documents
            metadata: New metadata
            
        Returns:
            True if successful, False otherwise
        """
        pass
