"""
ChromaDB Vector Store Implementation

MVP implementation using ChromaDB for local vector storage.
"""

from typing import List, Dict, Any, Optional
import logging
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class ChromaDBStore(VectorStore):
    """ChromaDB implementation for MVP"""
    
    def __init__(self, persist_directory: str):
        """
        Initialize ChromaDB store
        
        Args:
            persist_directory: Directory path for persistent storage
        """
        try:
            import chromadb
            self.client = chromadb.PersistentClient(path=persist_directory)
            logger.info(f"ChromaDB initialized with persist directory: {persist_directory}")
        except ImportError:
            logger.error("chromadb package not installed. Install with: pip install chromadb")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise
        
    def create_collection(self, name: str, dimension: int, metadata_schema: Dict[str, Any]) -> bool:
        """Creates a new collection for storing embeddings"""
        try:
            self.client.get_or_create_collection(
                name=name,
                metadata={"dimension": dimension, **metadata_schema}
            )
            logger.info(f"Collection '{name}' created/retrieved with dimension {dimension}")
            return True
        except Exception as e:
            logger.error(f"Failed to create collection '{name}': {e}")
            return False
        
    def add_embeddings(
        self, 
        collection: str,
        ids: List[str], 
        embeddings: List[List[float]], 
        documents: List[str],
        metadata: List[Dict[str, Any]]
    ) -> bool:
        """Adds embeddings to a collection"""
        try:
            coll = self.client.get_collection(collection)
            coll.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadata
            )
            logger.info(f"Added {len(ids)} embeddings to collection '{collection}'")
            return True
        except Exception as e:
            logger.error(f"Failed to add embeddings to '{collection}': {e}")
            return False
        
    def search(
        self,
        collection: str,
        query_embedding: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Searches for similar embeddings"""
        try:
            coll = self.client.get_collection(collection)
            results = coll.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filters
            )
            return self._format_results(results)
        except Exception as e:
            logger.error(f"Search failed in collection '{collection}': {e}")
            return []
    
    def delete_by_id(self, collection: str, ids: List[str]) -> bool:
        """Deletes embeddings by ID"""
        try:
            coll = self.client.get_collection(collection)
            coll.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} embeddings from collection '{collection}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete from '{collection}': {e}")
            return False
    
    def update_embeddings(
        self,
        collection: str,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadata: List[Dict[str, Any]]
    ) -> bool:
        """Updates existing embeddings"""
        try:
            coll = self.client.get_collection(collection)
            coll.update(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadata
            )
            logger.info(f"Updated {len(ids)} embeddings in collection '{collection}'")
            return True
        except Exception as e:
            logger.error(f"Failed to update embeddings in '{collection}': {e}")
            return False
    
    def _format_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Formats ChromaDB results to standard format"""
        formatted = []
        if not results or 'ids' not in results or not results['ids']:
            return formatted
        
        # ChromaDB returns results as lists of lists (one per query)
        ids = results['ids'][0] if results['ids'] else []
        distances = results['distances'][0] if results.get('distances') else []
        documents = results['documents'][0] if results.get('documents') else []
        metadatas = results['metadatas'][0] if results.get('metadatas') else []
        
        for i, id_val in enumerate(ids):
            formatted.append({
                'id': id_val,
                'score': 1 - distances[i] if i < len(distances) else 0,  # Convert distance to similarity
                'document': documents[i] if i < len(documents) else '',
                'metadata': metadatas[i] if i < len(metadatas) else {}
            })
        
        return formatted
