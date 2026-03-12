"""
Cache module for query result caching.

This module provides intelligent caching for query results with:
- Configurable TTL
- Semantic cache key generation
- File-based cache invalidation
- Cache bypass support

Key Components:
- QueryCache: Main cache service for query results
- QueryCacheConfig: Configuration for cache behavior
- CacheInvalidationService: Service for invalidating cache on re-indexing
"""

from src.cache.invalidation_service import CacheInvalidationService
from src.cache.query_cache import QueryCache, QueryCacheConfig

__all__ = ["QueryCache", "QueryCacheConfig", "CacheInvalidationService"]
