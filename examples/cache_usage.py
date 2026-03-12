"""
Example: Using the Cache Service

Demonstrates how to use the pluggable cache abstraction for
caching preprocessing results, embeddings, and query results.
"""

from src.config import AppConfig
from src.abstractions import CacheServiceFactory
import time


def main():
    """Demonstrate cache service usage"""
    
    # Load configuration
    config = AppConfig.from_env()
    
    print("=" * 70)
    print("Cache Service Demo")
    print("=" * 70)
    
    # Create cache service from configuration
    print(f"\n1. Creating cache service (backend: {config.cache.backend})...")
    cache = CacheServiceFactory.create(
        config.cache.backend,
        config.cache.config
    )
    print(f"   ✓ Cache service created")
    
    # Test basic operations
    print("\n2. Testing basic cache operations...")
    
    # Set a value
    cache.set("test:key1", "Hello, World!", ttl=60)
    print("   ✓ Set: test:key1 = 'Hello, World!' (TTL: 60s)")
    
    # Get the value
    value = cache.get("test:key1")
    print(f"   ✓ Get: test:key1 = '{value}'")
    
    # Check existence
    exists = cache.exists("test:key1")
    print(f"   ✓ Exists: test:key1 = {exists}")
    
    # Test cache miss
    missing = cache.get("test:nonexistent")
    print(f"   ✓ Cache miss: test:nonexistent = {missing}")
    
    # Test batch operations
    print("\n3. Testing batch operations...")
    
    items = {
        "test:batch1": "value1",
        "test:batch2": "value2",
        "test:batch3": "value3"
    }
    cache.set_many(items, ttl=120)
    print(f"   ✓ Set {len(items)} items in batch")
    
    keys = list(items.keys())
    values = cache.get_many(keys)
    print(f"   ✓ Got {len(values)} items in batch")
    for key, value in zip(keys, values):
        print(f"      {key} = {value}")
    
    # Test counter increment
    print("\n4. Testing counter operations...")
    
    cache.set("test:counter", 0)
    for i in range(5):
        new_value = cache.increment("test:counter")
        print(f"   ✓ Increment: test:counter = {new_value}")
    
    # Test pattern-based clearing
    print("\n5. Testing pattern-based clearing...")
    
    # Set some test data
    cache.set("test:temp1", "data1")
    cache.set("test:temp2", "data2")
    cache.set("other:data", "data3")
    
    # Clear only test:* keys
    cleared = cache.clear("test:*")
    print(f"   ✓ Cleared {cleared} keys matching 'test:*'")
    
    # Verify
    print(f"   ✓ test:temp1 exists: {cache.exists('test:temp1')}")
    print(f"   ✓ other:data exists: {cache.exists('other:data')}")
    
    # Get cache statistics
    print("\n6. Cache statistics...")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Demonstrate real-world use cases
    print("\n7. Real-world use cases...")
    
    # Use case 1: Cache preprocessing results
    print("\n   Use Case 1: Text Preprocessing Cache")
    text = "หาพนักงานชื่อพิมล"
    cache_key = f"preprocessing:{hash(text)}"
    
    # Check cache first
    cached_result = cache.get(cache_key)
    if cached_result:
        print(f"   ✓ Cache hit! Preprocessed: {cached_result}")
    else:
        print(f"   ✗ Cache miss, preprocessing...")
        # Simulate preprocessing
        time.sleep(0.1)
        preprocessed = ["หา", "พนักงาน", "ชื่อ", "พิมล"]
        cache.set(cache_key, preprocessed, ttl=3600)  # 1 hour
        print(f"   ✓ Cached result: {preprocessed}")
    
    # Use case 2: Cache embeddings
    print("\n   Use Case 2: Embedding Cache")
    query = "Find employee named Pimon"
    embedding_key = f"embedding:{hash(query)}"
    
    cached_embedding = cache.get(embedding_key)
    if cached_embedding:
        print(f"   ✓ Cache hit! Embedding: {cached_embedding[:5]}... (truncated)")
    else:
        print(f"   ✗ Cache miss, generating embedding...")
        # Simulate embedding generation
        time.sleep(0.2)
        embedding = [0.1, 0.2, 0.3] * 512  # Fake 1536-dim embedding
        cache.set(embedding_key, embedding, ttl=86400)  # 24 hours
        print(f"   ✓ Cached embedding ({len(embedding)} dimensions)")
    
    # Use case 3: Cache query results
    print("\n   Use Case 3: Query Results Cache")
    query_hash = hash("Show employees with last name Wongdee")
    result_key = f"query_result:{query_hash}"
    
    cached_results = cache.get(result_key)
    if cached_results:
        print(f"   ✓ Cache hit! Results: {cached_results}")
    else:
        print(f"   ✗ Cache miss, executing query...")
        # Simulate query execution
        time.sleep(0.3)
        results = {
            "employees": [
                {"id": 1, "name": "Pimon Wongdee"},
                {"id": 3, "name": "Wichai Wongdee"}
            ],
            "count": 2
        }
        cache.set(result_key, results, ttl=300)  # 5 minutes
        print(f"   ✓ Cached results: {results['count']} employees")
    
    # Clean up
    print("\n8. Cleaning up test data...")
    cache.clear("test:*")
    cache.clear("preprocessing:*")
    cache.clear("embedding:*")
    cache.clear("query_result:*")
    print("   ✓ Test data cleared")
    
    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    
    print("\n💡 Cache Benefits:")
    print("   • Faster response times (avoid reprocessing)")
    print("   • Reduced API costs (cache embeddings)")
    print("   • Better user experience (instant results)")
    print("   • Scalable (Redis for distributed systems)")
    
    print("\n💡 Migration Path:")
    print("   Development: CACHE_BACKEND=memory (simple, no setup)")
    print("   Production:  CACHE_BACKEND=redis (distributed, persistent)")


if __name__ == "__main__":
    main()
