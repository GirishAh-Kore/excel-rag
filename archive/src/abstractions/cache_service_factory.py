"""
Cache Service Factory

Factory for creating cache service instances based on configuration.
"""

from typing import Dict, Any
import logging
from .cache_service import CacheService
from .redis_cache import RedisCache
from .memory_cache import MemoryCache

logger = logging.getLogger(__name__)


class CacheServiceFactory:
    """Factory for creating cache service instances"""
    
    @staticmethod
    def create(backend: str, config: Dict[str, Any]) -> CacheService:
        """
        Create a cache service instance based on backend type
        
        Args:
            backend: Backend type ("redis" or "memory")
            config: Configuration dictionary for the backend
            
        Returns:
            CacheService instance
            
        Raises:
            ValueError: If backend is unknown or config is invalid
        """
        backend = backend.lower()
        
        try:
            if backend == "redis":
                host = config.get("host", "localhost")
                port = config.get("port", 6379)
                db = config.get("db", 0)
                password = config.get("password")
                prefix = config.get("prefix", "rag:")
                serializer = config.get("serializer", "json")
                
                logger.info(f"Creating Redis cache at {host}:{port}")
                return RedisCache(
                    host=host,
                    port=port,
                    db=db,
                    password=password,
                    prefix=prefix,
                    serializer=serializer
                )
            
            elif backend == "memory":
                max_size = config.get("max_size", 1000)
                default_ttl = config.get("default_ttl", 3600)
                
                logger.info(f"Creating in-memory cache (max_size={max_size})")
                return MemoryCache(
                    max_size=max_size,
                    default_ttl=default_ttl
                )
            
            else:
                raise ValueError(
                    f"Unknown cache backend: {backend}. "
                    f"Supported backends: 'redis', 'memory'"
                )
        
        except Exception as e:
            logger.error(f"Failed to create cache service for backend '{backend}': {e}")
            
            # Fallback to memory cache if Redis fails
            if backend == "redis":
                logger.warning("Falling back to in-memory cache")
                return MemoryCache(max_size=1000, default_ttl=3600)
            
            raise
