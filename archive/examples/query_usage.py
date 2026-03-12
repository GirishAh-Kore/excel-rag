"""
Query Processing Usage Example

This script demonstrates how to use the query processing components
to analyze queries, perform semantic search, manage conversation context,
and orchestrate the complete query pipeline.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import AppConfig
from src.abstractions.llm_service_factory import LLMServiceFactory
from src.abstractions.embedding_service_factory import EmbeddingServiceFactory
from src.abstractions.cache_service_factory import CacheServiceFactory
from src.abstractions.vector_store_factory import VectorStoreFactory
from src.indexing.vector_storage import VectorStorageManager
from src.query import (
    QueryEngine,
    QueryAnalyzer,
    SemanticSearcher,
    ConversationManager,
    ClarificationGenerator
)


def example_query_analyzer():
    """Example: Using QueryAnalyzer to analyze queries."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Query Analysis")
    print("="*60)
    
    # Load config and create LLM service
    config = AppConfig.from_env()
    llm_service = LLMServiceFactory.create(
        config.llm.provider,
        config.llm.config
    )
    
    # Create analyzer
    analyzer = QueryAnalyzer(llm_service)
    
    # Analyze different types of queries
    queries = [
        "What were the total expenses in January 2024?",
        "Compare revenue between Q1 and Q2",
        "How is the profit calculated in the summary sheet?",
        "Show me all files with marketing expenses"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        analysis = analyzer.analyze(query)
        
        print(f"  Intent: {analysis.intent}")
        print(f"  Is Comparison: {analysis.is_comparison}")
        print(f"  Entities: {analysis.entities}")
        print(f"  Data Types: {analysis.data_types_requested}")
        print(f"  Temporal Refs: {len(analysis.temporal_refs)}")
        print(f"  Confidence: {analysis.confidence:.2f}")


def example_semantic_search():
    """Example: Using SemanticSearcher to find relevant data."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Semantic Search")
    print("="*60)
    
    # Load config and create services
    config = AppConfig.from_env()
    
    embedding_service = EmbeddingServiceFactory.create(
        config.embedding.provider,
        config.embedding.config
    )
    
    vector_store = VectorStoreFactory.create(
        config.vector_store.provider,
        config.vector_store.config
    )
    
    vector_storage = VectorStorageManager(vector_store)
    
    # Create searcher
    searcher = SemanticSearcher(embedding_service, vector_storage)
    
    # Perform search
    query = "monthly revenue report"
    print(f"\nSearching for: {query}")
    
    results = searcher.search(query=query, top_k=5)
    
    print(f"\nFound {results.total_results} results:")
    for i, result in enumerate(results.results, 1):
        print(f"\n{i}. {result.file_name}")
        print(f"   Sheet: {result.sheet_name}")
        print(f"   Score: {result.score:.3f}")
        print(f"   Type: {result.content_type}")
        print(f"   Path: {result.file_path}")


def example_conversation_management():
    """Example: Using ConversationManager for context."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Conversation Management")
    print("="*60)
    
    # Load config and create cache service
    config = AppConfig.from_env()
    cache_service = CacheServiceFactory.create(
        config.cache.provider,
        config.cache.config
    )
    
    # Create manager
    manager = ConversationManager(cache_service)
    
    # Create a session
    session_id = manager.create_session()
    print(f"\nCreated session: {session_id}")
    
    # Simulate a conversation
    queries = [
        "What were the expenses in January?",
        "What about February?",
        "Compare them"
    ]
    
    for query in queries:
        print(f"\nUser: {query}")
        
        # Update context
        manager.update_context(
            session_id=session_id,
            query=query,
            selected_file="file123" if "January" in query else None
        )
        
        # Resolve ambiguous references
        resolved = manager.resolve_ambiguous_reference(query, session_id)
        if resolved:
            print(f"  Resolved references: {resolved}")
    
    # Get session stats
    stats = manager.get_session_stats(session_id)
    print(f"\nSession Stats:")
    print(f"  Query count: {stats['query_count']}")
    print(f"  File count: {stats['file_count']}")
    print(f"  Age: {stats['age_seconds']:.1f} seconds")


def example_clarification():
    """Example: Using ClarificationGenerator for ambiguous queries."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Clarification Generation")
    print("="*60)
    
    # Load config and create services
    config = AppConfig.from_env()
    
    llm_service = LLMServiceFactory.create(
        config.llm.provider,
        config.llm.config
    )
    
    embedding_service = EmbeddingServiceFactory.create(
        config.embedding.provider,
        config.embedding.config
    )
    
    vector_store = VectorStoreFactory.create(
        config.vector_store.provider,
        config.vector_store.config
    )
    
    vector_storage = VectorStorageManager(vector_store)
    
    # Create components
    searcher = SemanticSearcher(embedding_service, vector_storage)
    generator = ClarificationGenerator(llm_service)
    
    # Search for ambiguous query
    query = "expenses report"
    print(f"\nQuery: {query}")
    
    results = searcher.search(query=query, top_k=10)
    
    # Check if clarification needed
    if generator.needs_clarification(results, confidence=0.65):
        print("\nClarification needed!")
        
        # Generate clarification
        clarification = generator.generate_file_clarification(
            query=query,
            search_results=results,
            max_options=3
        )
        
        print(f"\n{clarification.question}")
        for i, option in enumerate(clarification.options, 1):
            print(f"{i}. {option.label}")
            if option.description:
                print(f"   {option.description}")
        
        # Simulate user response
        user_response = "1"
        print(f"\nUser selects: {user_response}")
        
        resolved = generator.handle_clarification_response(
            clarification_request=clarification,
            user_response=user_response
        )
        
        if resolved:
            print(f"Selected: {resolved['label']}")


def example_complete_pipeline():
    """Example: Using QueryEngine for complete pipeline."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Complete Query Pipeline")
    print("="*60)
    
    # Load config and create all services
    config = AppConfig.from_env()
    
    llm_service = LLMServiceFactory.create(
        config.llm.provider,
        config.llm.config
    )
    
    embedding_service = EmbeddingServiceFactory.create(
        config.embedding.provider,
        config.embedding.config
    )
    
    cache_service = CacheServiceFactory.create(
        config.cache.provider,
        config.cache.config
    )
    
    vector_store = VectorStoreFactory.create(
        config.vector_store.provider,
        config.vector_store.config
    )
    
    vector_storage = VectorStorageManager(vector_store)
    
    # Create query engine
    query_engine = QueryEngine(
        llm_service=llm_service,
        embedding_service=embedding_service,
        cache_service=cache_service,
        vector_storage=vector_storage
    )
    
    # Process queries
    queries = [
        "What were the total expenses in January 2024?",
        "What about February?",  # Follow-up question
        "Compare them"  # Comparison using context
    ]
    
    session_id = None
    
    for query in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print('='*60)
        
        # Process query
        result = query_engine.process_query(
            query=query,
            session_id=session_id
        )
        
        # Store session ID for follow-ups
        if not session_id:
            # Extract session ID from result (would be added to QueryResult)
            session_id = "demo_session"
        
        print(f"\nAnswer: {result.answer}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Processing time: {result.processing_time_ms}ms")
        print(f"Is comparison: {result.is_comparison}")
        
        if result.clarification_needed:
            print(f"\nClarification needed:")
            for question in result.clarifying_questions:
                print(f"  {question}")
        
        if result.sources:
            print(f"\nSources:")
            for source in result.sources:
                print(f"  - {source.file_name} / {source.sheet_name} / {source.cell_range}")


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("QUERY PROCESSING USAGE EXAMPLES")
    print("="*60)
    
    try:
        # Check if required environment variables are set
        required_vars = ["LLM_API_KEY", "EMBEDDING_API_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print(f"\nError: Missing required environment variables: {missing_vars}")
            print("Please set them in your .env file")
            return
        
        # Run examples
        example_query_analyzer()
        example_semantic_search()
        example_conversation_management()
        example_clarification()
        example_complete_pipeline()
        
        print("\n" + "="*60)
        print("All examples completed successfully!")
        print("="*60)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
