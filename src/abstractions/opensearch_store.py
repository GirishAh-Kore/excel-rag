"""
OpenSearch Vector Store Implementation

Production implementation using OpenSearch for scalable vector storage.
"""

from typing import List, Dict, Any, Optional
import logging
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class OpenSearchStore(VectorStore):
    """OpenSearch implementation for production"""
    
    def __init__(self, host: str, port: int, username: str, password: str, use_ssl: bool = True):
        """
        Initialize OpenSearch store
        
        Args:
            host: OpenSearch host
            port: OpenSearch port
            username: Authentication username
            password: Authentication password
            use_ssl: Whether to use SSL/TLS
        """
        try:
            from opensearchpy import OpenSearch
            self.client = OpenSearch(
                hosts=[{'host': host, 'port': port}],
                http_auth=(username, password),
                use_ssl=use_ssl,
                verify_certs=use_ssl,
                ssl_show_warn=False
            )
            logger.info(f"OpenSearch initialized at {host}:{port}")
        except ImportError:
            logger.error("opensearch-py package not installed. Install with: pip install opensearch-py")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize OpenSearch: {e}")
            raise
        
    def create_collection(self, name: str, dimension: int, metadata_schema: Dict[str, Any]) -> bool:
        """Creates a new index for storing embeddings"""
        try:
            if self.client.indices.exists(index=name):
                logger.info(f"Index '{name}' already exists")
                return True
            
            index_body = {
                "settings": {
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 100
                    }
                },
                "mappings": {
                    "properties": {
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": dimension,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib",
                                "parameters": {
                                    "ef_construction": 128,
                                    "m": 24
                                }
                            }
                        },
                        "document": {"type": "text"},
                        "metadata": {"type": "object", "enabled": True}
                    }
                }
            }
            
            self.client.indices.create(index=name, body=index_body)
            logger.info(f"Index '{name}' created with dimension {dimension}")
            return True
        except Exception as e:
            logger.error(f"Failed to create index '{name}': {e}")
            return False
        
    def add_embeddings(
        self, 
        collection: str,
        ids: List[str], 
        embeddings: List[List[float]], 
        documents: List[str],
        metadata: List[Dict[str, Any]]
    ) -> bool:
        """Adds embeddings to an index"""
        try:
            bulk_data = []
            for id_val, emb, doc, meta in zip(ids, embeddings, documents, metadata):
                bulk_data.append({"index": {"_index": collection, "_id": id_val}})
                bulk_data.append({
                    "embedding": emb,
                    "document": doc,
                    "metadata": meta
                })
            
            response = self.client.bulk(body=bulk_data, refresh=True)
            
            if response.get('errors'):
                logger.warning(f"Some documents failed to index in '{collection}'")
                return False
            
            logger.info(f"Added {len(ids)} embeddings to index '{collection}'")
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
            query = {
                "size": top_k,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": top_k
                        }
                    }
                }
            }
            
            if filters:
                query["query"] = {
                    "bool": {
                        "must": [query["query"]],
                        "filter": self._build_filters(filters)
                    }
                }
            
            results = self.client.search(index=collection, body=query)
            return self._format_results(results)
        except Exception as e:
            logger.error(f"Search failed in index '{collection}': {e}")
            return []
    
    def delete_by_id(self, collection: str, ids: List[str]) -> bool:
        """Deletes embeddings by ID"""
        try:
            bulk_data = []
            for id_val in ids:
                bulk_data.append({"delete": {"_index": collection, "_id": id_val}})
            
            response = self.client.bulk(body=bulk_data, refresh=True)
            
            if response.get('errors'):
                logger.warning(f"Some documents failed to delete from '{collection}'")
                return False
            
            logger.info(f"Deleted {len(ids)} embeddings from index '{collection}'")
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
            bulk_data = []
            for id_val, emb, doc, meta in zip(ids, embeddings, documents, metadata):
                bulk_data.append({"update": {"_index": collection, "_id": id_val}})
                bulk_data.append({
                    "doc": {
                        "embedding": emb,
                        "document": doc,
                        "metadata": meta
                    },
                    "doc_as_upsert": True
                })
            
            response = self.client.bulk(body=bulk_data, refresh=True)
            
            if response.get('errors'):
                logger.warning(f"Some documents failed to update in '{collection}'")
                return False
            
            logger.info(f"Updated {len(ids)} embeddings in index '{collection}'")
            return True
        except Exception as e:
            logger.error(f"Failed to update embeddings in '{collection}': {e}")
            return False
    
    def _build_filters(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Converts filter dict to OpenSearch filter format"""
        filter_clauses = []
        for key, value in filters.items():
            if isinstance(value, list):
                filter_clauses.append({"terms": {f"metadata.{key}": value}})
            else:
                filter_clauses.append({"term": {f"metadata.{key}": value}})
        return filter_clauses
    
    def _format_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Formats OpenSearch results to standard format"""
        formatted = []
        hits = results.get('hits', {}).get('hits', [])
        
        for hit in hits:
            formatted.append({
                'id': hit['_id'],
                'score': hit['_score'],
                'document': hit['_source'].get('document', ''),
                'metadata': hit['_source'].get('metadata', {})
            })
        
        return formatted
