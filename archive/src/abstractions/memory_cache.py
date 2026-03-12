"""
In-Memory Cache Implementation

Simple in-memory caching for MVP/development and fallback.
"""

from typing import Any, Optional, List
import logging
import time
from collections import OrderedDict
from threading import Lock
from .cache_service import CacheService

logger = logging.getLogger(__name__)


class MemoryCache(CacheService):
    """In-memory cache implementation with LRU eviction"""
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[int] = 3600):
        """
        Initialize in-memory cache
        
        Args:
            max_size: Maximum number of entries
            default_ttl: Default TTL in seconds (None = no expiration)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, tuple[Any, Optional[float]]] = OrderedDict()
        self._lock = Lock()
        
        # Stats tracking
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
        logger.info(f"In-memory cache initialized (max_size={max_size}, default_ttl={default_ttl})")
    
    def _is_expired(self, expiry: Optional[float]) -> bool:
        """Check if entry is expired"""
        if expiry is None:
            return False
        return time.time() > expiry
    
    def _evict_if_needed(self):
        """Evict oldest entry if cache is full"""
        if len(self._cache) >= self.max_size:
            # Remove oldest entry (FIFO)
            self._cache.popitem(last=False)
            self._evictions += 1
    
    def _clean_expired(self):
        """Remove expired entries (lazy cleanup)"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, expiry) in self._cache.items()
            if expiry is not None and current_time > expiry
        ]
        for key in expired_keys:
            del self._cache[key]
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                logger.debug(f"Cache miss: {key}")
                return None
            
            value, expiry = self._cache[key]
            
            # Check expiration
            if self._is_expired(expiry):
                del self._cache[key]
                self._misses += 1
                logger.debug(f"Cache miss (expired): {key}")
                return None
            
            # Move to end (LRU)
            self._cache.move_to_end(key)
            self._hits += 1
            logger.debug(f"Cache hit: {key}")
            return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        with self._lock:
            # Calculate expiry
            if ttl is None:
                ttl = self.default_ttl
            
            expiry = time.time() + ttl if ttl else None
            
            # Evict if needed
            if key not in self._cache:
                self._evict_if_needed()
            
            # Store value
            self._cache[key] = (value, expiry)
            self._cache.move_to_end(key)
            
            logger.debug(f"Cache set: {key} (ttl={ttl})")
            return True
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache delete: {key}")
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        with self._lock:
            if key not in self._cache:
                return False
            
            _, expiry = self._cache[key]
            if self._is_expired(expiry):
                del self._cache[key]
                return False
            
            return True
    
    def clear(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries"""
        with self._lock:
            if pattern:
                # Clear keys matching pattern (simple prefix matching)
                pattern = pattern.replace('*', '')
                keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
                count = len(keys_to_delete)
                for key in keys_to_delete:
                    del self._cache[key]
                logger.info(f"Cleared {count} cache entries matching '{pattern}'")
                return count
            else:
                # Clear all
                count = len(self._cache)
                self._cache.clear()
                logger.info(f"Cleared {count} cache entries")
                return count
    
    def get_many(self, keys: List[str]) -> List[Optional[Any]]:
        """Get multiple values from cache"""
        results = []
        for key in keys:
            results.append(self.get(key))
        
        hits = sum(1 for r in results if r is not None)
        logger.debug(f"Cache get_many: {len(keys)} keys, {hits} hits")
        return results
    
    def set_many(self, items: dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values in cache"""
        for key, value in items.items():
            self.set(key, value, ttl)
        
        logger.debug(f"Cache set_many: {len(items)} items (ttl={ttl})")
        return True
    
    def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter"""
        with self._lock:
            current = 0
            if key in self._cache:
                value, expiry = self._cache[key]
                if not self._is_expired(expiry) and isinstance(value, int):
                    current = value
            
            new_value = current + amount
            self._cache[key] = (new_value, None)
            self._cache.move_to_end(key)
            
            logger.debug(f"Cache increment: {key} by {amount} = {new_value}")
            return new_value
    
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            # Clean expired entries for accurate count
            self._clean_expired()
            
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "backend": "memory",
                "connected": True,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.2f}%",
                "total_keys": len(self._cache),
                "max_size": self.max_size,
                "evictions": self._evictions,
                "utilization": f"{len(self._cache) / self.max_size * 100:.1f}%"
            }
