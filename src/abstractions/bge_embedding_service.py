"""
BGE-M3 Embedding Service

Open-source multilingual embedding model from BAAI.
Supports dense, sparse, and multi-vector retrieval.
"""

import logging
from typing import List, Optional

from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class BGEEmbeddingService(EmbeddingService):
    """
    BGE-M3 embedding service using FlagEmbedding or sentence-transformers.
    
    BGE-M3 features:
    - Multilingual (100+ languages)
    - 1024 dimensions
    - Supports dense, sparse, and ColBERT retrieval
    - State-of-the-art performance
    - Runs locally (no API costs)
    """
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        use_fp16: bool = True,
        device: Optional[str] = None,
        max_length: int = 8192
    ):
        """
        Initialize BGE-M3 embedding service.
        
        Args:
            model_name: Model name/path (default: BAAI/bge-m3)
            use_fp16: Use half precision for faster inference
            device: Device to use (cuda, cpu, mps). Auto-detected if None.
            max_length: Maximum sequence length
        """
        self.model_name = model_name
        self.use_fp16 = use_fp16
        self.max_length = max_length
        self._model = None
        self._device = device
        
    def _ensure_loaded(self):
        """Lazy load the model."""
        if self._model is not None:
            return
            
        try:
            # Try FlagEmbedding first (official implementation)
            from FlagEmbedding import BGEM3FlagModel
            
            self._model = BGEM3FlagModel(
                self.model_name,
                use_fp16=self.use_fp16,
                device=self._device
            )
            self._backend = "flag"
            logger.info(f"Loaded BGE-M3 via FlagEmbedding: {self.model_name}")
            
        except ImportError:
            # Fallback to sentence-transformers
            try:
                from sentence_transformers import SentenceTransformer
                
                device = self._device
                if device is None:
                    import torch
                    if torch.cuda.is_available():
                        device = "cuda"
                    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                        device = "mps"
                    else:
                        device = "cpu"
                
                self._model = SentenceTransformer(
                    self.model_name,
                    device=device
                )
                self._backend = "sentence-transformers"
                logger.info(
                    f"Loaded BGE-M3 via sentence-transformers: {self.model_name} on {device}"
                )
                
            except ImportError as e:
                logger.error(
                    "Neither FlagEmbedding nor sentence-transformers installed. "
                    "Install with: pip install FlagEmbedding or pip install sentence-transformers"
                )
                raise ImportError(
                    "BGE-M3 requires FlagEmbedding or sentence-transformers. "
                    "Install: pip install FlagEmbedding"
                ) from e
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        self._ensure_loaded()
        
        if self._backend == "flag":
            result = self._model.encode(
                [text],
                max_length=self.max_length,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False
            )
            return result['dense_vecs'][0].tolist()
        else:
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        self._ensure_loaded()
        
        if self._backend == "flag":
            result = self._model.encode(
                texts,
                max_length=self.max_length,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False
            )
            return [vec.tolist() for vec in result['dense_vecs']]
        else:
            embeddings = self._model.encode(texts, convert_to_numpy=True)
            return [emb.tolist() for emb in embeddings]
    
    def embed_with_sparse(self, texts: List[str]) -> dict:
        """
        Generate both dense and sparse embeddings (BGE-M3 feature).
        
        Useful for hybrid search without BM25.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            Dict with 'dense' and 'sparse' embeddings
        """
        self._ensure_loaded()
        
        if self._backend != "flag":
            logger.warning("Sparse embeddings only available with FlagEmbedding backend")
            return {"dense": self.embed_batch(texts), "sparse": None}
        
        result = self._model.encode(
            texts,
            max_length=self.max_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False
        )
        
        return {
            "dense": [vec.tolist() for vec in result['dense_vecs']],
            "sparse": result['lexical_weights']
        }
    
    def get_model_name(self) -> str:
        """Return the model name."""
        return self.model_name
    
    def get_embedding_dimension(self) -> int:
        """Return embedding dimension (1024 for BGE-M3)."""
        return 1024
