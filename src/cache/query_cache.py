"""
Query Cache Module.

This module implements intelligent caching for query results with:
- Configurable TTL (default 1 hour)
- Semantic cache key generation for equivalent queries
- File ID tracking for cache invalidation
- Cache bypass support
- Cache hit indication in responses

Supports Requirements 43.1, 43.2, 43.3, 43.4, 43.5.
"""

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Optional, Protocol, runtime_checkable

from src.abstractions.cache_service import CacheService
from src.models.query_pipeline import QueryResponse

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class QueryCacheConfig:
    """
    Configuration for QueryCache.
    
    Attributes:
        default_ttl_seconds: Default TTL for cached entries (default 3600 = 1 hour).
        enable_semantic_keys: Enable semantic normalization for cache keys.
        max_key_length: Maximum length for cache keys.
        key_prefix: Prefix for all cache keys.
    """
    default_ttl_seconds: int = 3600
    enable_semantic_keys: bool = True
    max_key_length: int = 128
    key_prefix: str = "query_cache:"
    
    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.default_ttl_seconds <= 0:
            raise ValueError(
                f"default_ttl_seconds must be positive, got {self.default_ttl_seconds}"
            )
        if self.max_key_length <= 0:
            raise ValueError(
                f"max_key_length must be positive, got {self.max_key_length}"
            )


# =============================================================================
# Protocols
# =============================================================================


@runtime_checkable
class FileIndexTrackerProtocol(Protocol):
    """
    Protocol for tracking file indexing events.
    
    Used to detect when files are re-indexed for cache invalidation.
    """
    
    def get_file_indexed_at(self, file_id: str) -> Optional[float]:
        """Get timestamp when file was last indexed."""
        ...


# =============================================================================
# Cache Entry Model
# =============================================================================


@dataclass
class CacheEntry:
    """
    Cached query result entry.
    
    Attributes:
        response: The cached QueryResponse.
        query_text: Original query text.
        file_ids: List of file IDs involved in the response.
        created_at: Timestamp when entry was created.
        expires_at: Timestamp when entry expires.
    """
    response: dict[str, Any]
    query_text: str
    file_ids: list[str]
    created_at: float
    expires_at: float
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() > self.expires_at
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "response": self.response,
            "query_text": self.query_text,
            "file_ids": self.file_ids,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        return cls(
            response=data["response"],
            query_text=data["query_text"],
            file_ids=data["file_ids"],
            created_at=data["created_at"],
            expires_at=data["expires_at"],
        )


# =============================================================================
# Query Cache
# =============================================================================


class QueryCache:
    """
    Intelligent cache for query results.
    
    Provides caching with semantic key generation, file-based invalidation,
    and cache bypass support. Uses an injected CacheService backend for
    actual storage (memory or Redis).
    
    Features:
    - Semantic cache key generation for equivalent queries
    - File ID tracking for targeted invalidation
    - Configurable TTL with per-query override
    - Cache bypass option
    - Cache hit indication in responses
    
    Implements Requirements:
    - 43.1: Cache query results with configurable TTL
    - 43.3: Intelligent cache key generation
    - 43.4: Support cache bypass option
    - 43.5: Indicate cache hit in responses
    
    Example:
        >>> cache = QueryCache(
        ...     cache_service=memory_cache,
        ...     config=QueryCacheConfig(default_ttl_seconds=3600)
        ... )
        >>> cache.set(query="total sales", response=response, file_ids=["file1"])
        >>> cached = cache.get(query="Total Sales")  # Semantic match
    """
    
    # Stopwords to remove for semantic normalization
    STOPWORDS = frozenset([
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "what", "which", "who", "whom", "this", "that", "these", "those",
        "am", "been", "being", "have", "has", "had", "do", "does", "did",
        "will", "would", "could", "should", "may", "might", "must", "shall",
        "can", "need", "dare", "ought", "used", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "under", "again",
        "further", "then", "once", "here", "there", "when", "where", "why",
        "how", "all", "each", "few", "more", "most", "other", "some", "such",
        "no", "nor", "not", "only", "own", "same", "so", "than", "too",
        "very", "just", "also", "now", "please", "show", "me", "tell", "give",
    ])
    
    def __init__(
        self,
        cache_service: CacheService,
        config: Optional[QueryCacheConfig] = None
    ) -> None:
        """
        Initialize QueryCache with injected dependencies.
        
        Args:
            cache_service: Backend cache service (memory or Redis).
            config: Optional configuration (uses defaults if not provided).
            
        Raises:
            ValueError: If cache_service is None.
        """
        if cache_service is None:
            raise ValueError("cache_service is required")
        
        self._cache_service = cache_service
        self._config = config or QueryCacheConfig()
        self._lock = Lock()
        
        # Track file_id -> cache_keys mapping for invalidation
        self._file_to_keys: dict[str, set[str]] = {}
        self._file_to_keys_lock = Lock()
        
        # Stats
        self._hits = 0
        self._misses = 0
        self._invalidations = 0
        
        logger.info(
            f"QueryCache initialized with TTL={self._config.default_ttl_seconds}s, "
            f"semantic_keys={self._config.enable_semantic_keys}"
        )


    # =========================================================================
    # Public API
    # =========================================================================

    def get(
        self,
        query: str,
        file_hints: Optional[list[str]] = None,
        sheet_hints: Optional[list[str]] = None,
        bypass_cache: bool = False
    ) -> Optional[QueryResponse]:
        """
        Get cached response for a query.
        
        Generates a semantic cache key and retrieves the cached response
        if available and not expired.
        
        Args:
            query: The query text.
            file_hints: Optional file hints used in the query.
            sheet_hints: Optional sheet hints used in the query.
            bypass_cache: If True, always return None (cache bypass).
            
        Returns:
            QueryResponse with from_cache=True if found, None otherwise.
            
        Implements Requirements 43.3, 43.4, 43.5.
        """
        if bypass_cache:
            logger.debug("Cache bypass requested")
            return None
        
        cache_key = self._generate_cache_key(query, file_hints, sheet_hints)
        
        try:
            cached_data = self._cache_service.get(cache_key)
            
            if cached_data is None:
                self._misses += 1
                logger.debug(f"Cache miss for query: {query[:50]}...")
                return None
            
            # Parse cache entry
            entry = CacheEntry.from_dict(cached_data)
            
            # Check expiration (double-check even though backend may handle it)
            if entry.is_expired():
                self._cache_service.delete(cache_key)
                self._misses += 1
                logger.debug(f"Cache entry expired for query: {query[:50]}...")
                return None
            
            # Reconstruct QueryResponse
            response = QueryResponse(**entry.response)
            response.from_cache = True
            
            self._hits += 1
            logger.info(f"Cache hit for query: {query[:50]}...")
            return response
            
        except Exception as e:
            logger.warning(f"Error retrieving from cache: {e}")
            self._misses += 1
            return None

    def set(
        self,
        query: str,
        response: QueryResponse,
        file_ids: list[str],
        file_hints: Optional[list[str]] = None,
        sheet_hints: Optional[list[str]] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache a query response.
        
        Stores the response with file ID tracking for later invalidation.
        
        Args:
            query: The query text.
            response: The QueryResponse to cache.
            file_ids: List of file IDs involved in generating the response.
            file_hints: Optional file hints used in the query.
            sheet_hints: Optional sheet hints used in the query.
            ttl: Optional TTL override in seconds.
            
        Returns:
            True if caching succeeded, False otherwise.
            
        Implements Requirements 43.1, 43.3.
        """
        cache_key = self._generate_cache_key(query, file_hints, sheet_hints)
        effective_ttl = ttl if ttl is not None else self._config.default_ttl_seconds
        
        try:
            # Create cache entry
            now = time.time()
            entry = CacheEntry(
                response=response.model_dump(),
                query_text=query,
                file_ids=file_ids,
                created_at=now,
                expires_at=now + effective_ttl,
            )
            
            # Store in cache
            success = self._cache_service.set(
                key=cache_key,
                value=entry.to_dict(),
                ttl=effective_ttl
            )
            
            if success:
                # Track file_id -> cache_key mapping for invalidation
                self._track_file_ids(cache_key, file_ids)
                logger.debug(
                    f"Cached query response: {query[:50]}... "
                    f"(ttl={effective_ttl}s, files={len(file_ids)})"
                )
            
            return success
            
        except Exception as e:
            logger.warning(f"Error caching response: {e}")
            return False

    def invalidate_by_file(self, file_id: str) -> int:
        """
        Invalidate all cache entries containing a specific file.
        
        Called when a file is re-indexed to ensure stale data is not served.
        
        Args:
            file_id: The file ID to invalidate cache entries for.
            
        Returns:
            Number of cache entries invalidated.
            
        Implements Requirement 43.2.
        """
        invalidated_count = 0
        
        with self._file_to_keys_lock:
            cache_keys = self._file_to_keys.pop(file_id, set())
        
        for cache_key in cache_keys:
            try:
                if self._cache_service.delete(cache_key):
                    invalidated_count += 1
            except Exception as e:
                logger.warning(f"Error invalidating cache key {cache_key}: {e}")
        
        if invalidated_count > 0:
            self._invalidations += invalidated_count
            logger.info(
                f"Invalidated {invalidated_count} cache entries for file_id={file_id}"
            )
        
        return invalidated_count

    def invalidate_by_files(self, file_ids: list[str]) -> int:
        """
        Invalidate cache entries for multiple files.
        
        Args:
            file_ids: List of file IDs to invalidate.
            
        Returns:
            Total number of cache entries invalidated.
        """
        total_invalidated = 0
        for file_id in file_ids:
            total_invalidated += self.invalidate_by_file(file_id)
        return total_invalidated

    def clear(self) -> int:
        """
        Clear all query cache entries.
        
        Returns:
            Number of entries cleared.
        """
        pattern = f"{self._config.key_prefix}*"
        count = self._cache_service.clear(pattern)
        
        with self._file_to_keys_lock:
            self._file_to_keys.clear()
        
        logger.info(f"Cleared {count} query cache entries")
        return count

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics.
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0.0
        
        backend_stats = self._cache_service.get_stats()
        
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "invalidations": self._invalidations,
            "tracked_files": len(self._file_to_keys),
            "default_ttl_seconds": self._config.default_ttl_seconds,
            "semantic_keys_enabled": self._config.enable_semantic_keys,
            "backend": backend_stats,
        }

    # =========================================================================
    # Cache Key Generation
    # =========================================================================

    def _generate_cache_key(
        self,
        query: str,
        file_hints: Optional[list[str]],
        sheet_hints: Optional[list[str]]
    ) -> str:
        """
        Generate cache key for a query.
        
        Uses semantic normalization to match equivalent queries.
        
        Args:
            query: The query text.
            file_hints: Optional file hints.
            sheet_hints: Optional sheet hints.
            
        Returns:
            Cache key string.
            
        Implements Requirement 43.3.
        """
        # Normalize query for semantic equivalence
        if self._config.enable_semantic_keys:
            normalized_query = self._normalize_query(query)
        else:
            normalized_query = query.lower().strip()
        
        # Build key components
        key_parts = [normalized_query]
        
        if file_hints:
            sorted_hints = sorted(h.lower() for h in file_hints)
            key_parts.append(f"files:{','.join(sorted_hints)}")
        
        if sheet_hints:
            sorted_hints = sorted(h.lower() for h in sheet_hints)
            key_parts.append(f"sheets:{','.join(sorted_hints)}")
        
        # Create hash
        key_string = "|".join(key_parts)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:32]
        
        return f"{self._config.key_prefix}{key_hash}"

    def _normalize_query(self, query: str) -> str:
        """
        Normalize query for semantic cache key generation.
        
        Applies transformations to match semantically equivalent queries:
        - Lowercase
        - Remove extra whitespace
        - Remove stopwords
        - Sort remaining words
        - Normalize numbers and dates
        
        Args:
            query: Original query text.
            
        Returns:
            Normalized query string.
        """
        # Lowercase and strip
        text = query.lower().strip()
        
        # Remove punctuation except for numbers
        text = re.sub(r'[^\w\s\d.]', ' ', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Tokenize
        words = text.split()
        
        # Remove stopwords
        words = [w for w in words if w not in self.STOPWORDS]
        
        # Sort for order-independence (e.g., "sales total" == "total sales")
        words.sort()
        
        return ' '.join(words)

    # =========================================================================
    # File ID Tracking
    # =========================================================================

    def _track_file_ids(self, cache_key: str, file_ids: list[str]) -> None:
        """
        Track file_id -> cache_key mapping for invalidation.
        
        Args:
            cache_key: The cache key.
            file_ids: List of file IDs associated with this cache entry.
        """
        with self._file_to_keys_lock:
            for file_id in file_ids:
                if file_id not in self._file_to_keys:
                    self._file_to_keys[file_id] = set()
                self._file_to_keys[file_id].add(cache_key)

    def _untrack_cache_key(self, cache_key: str) -> None:
        """
        Remove cache key from all file_id mappings.
        
        Args:
            cache_key: The cache key to remove.
        """
        with self._file_to_keys_lock:
            for file_id in list(self._file_to_keys.keys()):
                self._file_to_keys[file_id].discard(cache_key)
                if not self._file_to_keys[file_id]:
                    del self._file_to_keys[file_id]
