"""
Redis Cache Implementation

Production-ready caching with Redis for distributed systems.
"""

from typing import Any, Optional, List
import logging
import json
import pickle
from .cache_service import CacheService

logger = logging.getLogger(__name__)


class RedisCache(CacheService):
    """Redis cache implementation for production"""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 6379,
                 db: int = 0,
                 password: Optional[str] = None,
                 prefix: str = "rag:",
                 serializer: str = "json"):
        """
        Initialize Redis cache
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (if required)
            prefix: Key prefix for namespacing
            serializer: Serialization method ("json" or "pickle")
        """
        try:
            import redis
            self.redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=False  # We handle encoding ourselves
            )
            self.prefix = prefix
            self.serializer = serializer
            
            # Test connection
            self.redis.ping()
            logger.info(f"Redis cache initialized at {host}:{port} (db={db})")
            
            # Stats tracking
            self._hits = 0
            self._misses = 0
            
        except ImportError:
            logger.error("redis package not installed. Install with: pip install redis")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def _make_key(self, key: str) -> str:
        """Add prefix to key"""
        return f"{self.prefix}{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage"""
        if self.serializer == "json":
            return json.dumps(value).encode('utf-8')
        else:  # pickle
            return pickle.dumps(value)
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage"""
        if data is None:
            return None
        
        try:
            if self.serializer == "json":
                return json.loads(data.decode('utf-8'))
            else:  # pickle
                return pickle.loads(data)
        except Exception as e:
            logger.error(f"Failed to deserialize cached value: {e}")
            return None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            redis_key = self._make_key(key)
            data = self.redis.get(redis_key)
            
            if data is None:
                self._misses += 1
                logger.debug(f"Cache miss: {key}")
                return None
            
            self._hits += 1
            logger.debug(f"Cache hit: {key}")
            return self._deserialize(data)
            
        except Exception as e:
            logger.error(f"Redis get error for key '{key}': {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        try:
            redis_key = self._make_key(key)
            data = self._serialize(value)
            
            if ttl:
                self.redis.setex(redis_key, ttl, data)
            else:
                self.redis.set(redis_key, data)
            
            logger.debug(f"Cache set: {key} (ttl={ttl})")
            return True
            
        except Exception as e:
            logger.error(f"Redis set error for key '{key}': {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            redis_key = self._make_key(key)
            result = self.redis.delete(redis_key)
            logger.debug(f"Cache delete: {key} (existed={result > 0})")
            return result > 0
            
        except Exception as e:
            logger.error(f"Redis delete error for key '{key}': {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            redis_key = self._make_key(key)
            return self.redis.exists(redis_key) > 0
        except Exception as e:
            logger.error(f"Redis exists error for key '{key}': {e}")
            return False
    
    def clear(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries"""
        try:
            if pattern:
                # Clear keys matching pattern
                search_pattern = f"{self.prefix}{pattern}"
                keys = self.redis.keys(search_pattern)
                if keys:
                    count = self.redis.delete(*keys)
                    logger.info(f"Cleared {count} cache entries matching '{pattern}'")
                    return count
                return 0
            else:
                # Clear all keys with our prefix
                keys = self.redis.keys(f"{self.prefix}*")
                if keys:
                    count = self.redis.delete(*keys)
                    logger.info(f"Cleared {count} cache entries")
                    return count
                return 0
                
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return 0
    
    def get_many(self, keys: List[str]) -> List[Optional[Any]]:
        """Get multiple values from cache"""
        try:
            redis_keys = [self._make_key(k) for k in keys]
            values = self.redis.mget(redis_keys)
            
            results = []
            for i, data in enumerate(values):
                if data is None:
                    self._misses += 1
                    results.append(None)
                else:
                    self._hits += 1
                    results.append(self._deserialize(data))
            
            logger.debug(f"Cache get_many: {len(keys)} keys, {sum(1 for r in results if r is not None)} hits")
            return results
            
        except Exception as e:
            logger.error(f"Redis get_many error: {e}")
            return [None] * len(keys)
    
    def set_many(self, items: dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values in cache"""
        try:
            pipe = self.redis.pipeline()
            
            for key, value in items.items():
                redis_key = self._make_key(key)
                data = self._serialize(value)
                
                if ttl:
                    pipe.setex(redis_key, ttl, data)
                else:
                    pipe.set(redis_key, data)
            
            pipe.execute()
            logger.debug(f"Cache set_many: {len(items)} items (ttl={ttl})")
            return True
            
        except Exception as e:
            logger.error(f"Redis set_many error: {e}")
            return False
    
    def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter"""
        try:
            redis_key = self._make_key(key)
            new_value = self.redis.incrby(redis_key, amount)
            logger.debug(f"Cache increment: {key} by {amount} = {new_value}")
            return new_value
            
        except Exception as e:
            logger.error(f"Redis increment error for key '{key}': {e}")
            return 0
    
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        try:
            info = self.redis.info()
            
            # Calculate hit rate
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "backend": "redis",
                "connected": True,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.2f}%",
                "total_keys": self.redis.dbsize(),
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
        except Exception as e:
            logger.error(f"Redis get_stats error: {e}")
            return {
                "backend": "redis",
                "connected": False,
                "error": str(e)
            }
