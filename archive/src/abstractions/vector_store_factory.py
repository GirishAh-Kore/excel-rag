"""
Vector Store Factory

Factory for creating vector store instances based on configuration.
"""

from typing import Dict, Any
import logging
from .vector_store import VectorStore
from .chromadb_store import ChromaDBStore
from .opensearch_store import OpenSearchStore

logger = logging.getLogger(__name__)


class VectorStoreFactory:
    """Factory for creating vector store instances"""
    
    @staticmethod
    def create(store_type: str, config: Dict[str, Any]) -> VectorStore:
        """
        Creates a vector store instance based on type
        
        Args:
            store_type: Type of vector store ("chromadb" or "opensearch")
            config: Configuration dictionary for the store
            
        Returns:
            VectorStore instance
            
        Raises:
            ValueError: If store_type is unknown or config is invalid
        """
        store_type = store_type.lower()
        
        try:
            if store_type == "chromadb":
                persist_directory = config.get("persist_directory")
                if not persist_directory:
                    raise ValueError("ChromaDB requires 'persist_directory' in config")
                
                logger.info(f"Creating ChromaDB store with directory: {persist_directory}")
                return ChromaDBStore(persist_directory=persist_directory)
            
            elif store_type == "opensearch":
                host = config.get("host")
                port = config.get("port", 9200)
                username = config.get("username")
                password = config.get("password")
                use_ssl = config.get("use_ssl", True)
                
                if not host or not username or not password:
                    raise ValueError("OpenSearch requires 'host', 'username', and 'password' in config")
                
                logger.info(f"Creating OpenSearch store at {host}:{port}")
                return OpenSearchStore(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    use_ssl=use_ssl
                )
            
            else:
                raise ValueError(f"Unknown vector store type: {store_type}. Supported types: 'chromadb', 'opensearch'")
        
        except Exception as e:
            logger.error(f"Failed to create vector store of type '{store_type}': {e}")
            raise
