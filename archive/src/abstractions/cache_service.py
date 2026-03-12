"""
Cache Service Abstraction Layer

Provides a pluggable interface for caching implementations,
supporting Redis (production) and in-memory (MVP/development).
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class CacheService(ABC):
    """Abstract base class for cache implementations"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None = no expiration)
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete value from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists
        """
        pass
    
    @abstractmethod
    def clear(self, pattern: Optional[str] = None) -> int:
        """
        Clear cache entries
        
        Args:
            pattern: Optional pattern to match keys (e.g., "preprocessing:*")
                    If None, clears all entries
            
        Returns:
            Number of entries cleared
        """
        pass
    
    @abstractmethod
    def get_many(self, keys: List[str]) -> List[Optional[Any]]:
        """
        Get multiple values from cache
        
        Args:
            keys: List of cache keys
            
        Returns:
            List of values (None for missing keys)
        """
        pass
    
    @abstractmethod
    def set_many(self, items: dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Set multiple values in cache
        
        Args:
            items: Dictionary of key-value pairs
            ttl: Time to live in seconds
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment a counter
        
        Args:
            key: Cache key
            amount: Amount to increment by
            
        Returns:
            New value after increment
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache stats (hits, misses, size, etc.)
        """
        pass
