"""
Example: Using the Abstraction Layers

This example demonstrates how to use the pluggable abstraction layers
to easily switch between different providers without changing code.
"""

from src.config import AppConfig
from src.abstractions import (
    VectorStoreFactory,
    EmbeddingServiceFactory,
    LLMServiceFactory
)


def main():
    """Demonstrate abstraction layer usage"""
    
    # Load configuration from environment
    config = AppConfig.from_env()
    
    print("=" * 60)
    print("Google Drive Excel RAG - Abstraction Layer Demo")
    print("=" * 60)
    
    # Create services using factories
    print("\n1. Creating Vector Store...")
    try:
        vector_store = VectorStoreFactory.create(
            config.vector_store.provider,
            config.vector_store.config
        )
        print(f"   ✓ Vector Store: {config.vector_store.provider}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return
    
    print("\n2. Creating Embedding Service...")
    try:
        embedding_service = EmbeddingServiceFactory.create(
            config.embedding.provider,
            config.embedding.config
        )
        print(f"   ✓ Embedding Service: {embedding_service.get_model_name()}")
        print(f"   ✓ Embedding Dimension: {embedding_service.get_embedding_dimension()}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return
    
    print("\n3. Creating LLM Service...")
    try:
        llm_service = LLMServiceFactory.create(
            config.llm.provider,
            config.llm.config
        )
        print(f"   ✓ LLM Service: {llm_service.get_model_name()}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return
    
    print("\n4. Testing Embedding Service...")
    try:
        # Test single text embedding
        test_text = "What is the total revenue for Q1 2024?"
        embedding = embedding_service.embed_text(test_text)
        print(f"   ✓ Generated embedding with {len(embedding)} dimensions")
        
        # Test batch embedding
        test_texts = [
            "Revenue data for January",
            "Expense report for February",
            "Sales figures for March"
        ]
        embeddings = embedding_service.embed_batch(test_texts)
        print(f"   ✓ Generated {len(embeddings)} embeddings in batch")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
    
    print("\n5. Testing Vector Store...")
    try:
        # Create a test collection
        collection_name = "test_collection"
        dimension = embedding_service.get_embedding_dimension()
        
        success = vector_store.create_collection(
            name=collection_name,
            dimension=dimension,
            metadata_schema={"test": True}
        )
        
        if success:
            print(f"   ✓ Created collection '{collection_name}'")
        else:
            print(f"   ✗ Failed to create collection")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
    
    print("\n6. Testing LLM Service...")
    try:
        # Test text generation
        prompt = "Explain what a RAG system is in one sentence."
        response = llm_service.generate(
            prompt=prompt,
            system_prompt="You are a helpful assistant.",
            temperature=0.7,
            max_tokens=100
        )
        print(f"   ✓ Generated response: {response[:100]}...")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    
    print("\n💡 Migration Example:")
    print("   To switch from ChromaDB to OpenSearch:")
    print("   1. Update .env: VECTOR_STORE_PROVIDER=opensearch")
    print("   2. Set OpenSearch credentials in .env")
    print("   3. Restart application - no code changes needed!")
    
    print("\n   To switch from OpenAI to Claude:")
    print("   1. Update .env: LLM_PROVIDER=anthropic")
    print("   2. Set Anthropic API key in .env")
    print("   3. Restart application - no code changes needed!")


if __name__ == "__main__":
    main()
