"""
Example usage of file and sheet selection components.

This script demonstrates how to use FileSelector and SheetSelector
to rank and select files and sheets based on query relevance.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import AppConfig
from src.database.connection import DatabaseConnection
from src.abstractions.embedding_service_factory import EmbeddingServiceFactory
from src.indexing.vector_storage import VectorStorageManager
from src.indexing.metadata_storage import MetadataStorageManager
from src.query.query_analyzer import QueryAnalyzer
from src.query.semantic_searcher import SemanticSearcher
from src.query.file_selector import FileSelector
from src.query.sheet_selector import SheetSelector
from src.query.date_parser import DateParser
from src.query.preference_manager import PreferenceManager
from src.abstractions.llm_service_factory import LLMServiceFactory
from src.text_processing.preprocessor import TextPreprocessor


def main():
    """Demonstrate file and sheet selection."""
    
    print("=" * 80)
    print("File and Sheet Selection Example")
    print("=" * 80)
    
    # Load configuration
    config = AppConfig.from_env()
    
    # Initialize database connection
    db_connection = DatabaseConnection(config.database_path)
    
    # Initialize services
    embedding_service = EmbeddingServiceFactory.create(
        config.embedding.provider,
        config.embedding.config
    )
    
    llm_service = LLMServiceFactory.create(
        config.llm.provider,
        config.llm.config
    )
    
    # Initialize storage managers
    vector_storage = VectorStorageManager(
        vector_store_config=config.vector_store,
        embedding_service=embedding_service
    )
    
    metadata_storage = MetadataStorageManager(db_connection)
    
    # Initialize query components
    query_analyzer = QueryAnalyzer(llm_service)
    
    semantic_searcher = SemanticSearcher(
        embedding_service=embedding_service,
        vector_storage=vector_storage
    )
    
    # Initialize selection components
    date_parser = DateParser()
    preference_manager = PreferenceManager(db_connection)
    
    file_selector = FileSelector(
        metadata_storage=metadata_storage,
        date_parser=date_parser,
        preference_manager=preference_manager
    )
    
    text_preprocessor = TextPreprocessor(config)
    
    sheet_selector = SheetSelector(
        metadata_storage=metadata_storage,
        text_preprocessor=text_preprocessor
    )
    
    # Example query
    query = "What were the total expenses in January 2024?"
    
    print(f"\nQuery: {query}")
    print("-" * 80)
    
    # Step 1: Analyze query
    print("\n1. Analyzing query...")
    query_analysis = query_analyzer.analyze(query)
    
    print(f"   Intent: {query_analysis.intent}")
    print(f"   Entities: {query_analysis.entities}")
    print(f"   Temporal refs: {len(query_analysis.temporal_refs)}")
    print(f"   Is comparison: {query_analysis.is_comparison}")
    
    # Step 2: Semantic search
    print("\n2. Performing semantic search...")
    search_results = semantic_searcher.search(
        query=query,
        query_analysis=query_analysis,
        top_k=10
    )
    
    print(f"   Found {len(search_results.results)} results")
    
    if not search_results.results:
        print("\n   No results found. Make sure files are indexed first.")
        return
    
    # Step 3: Rank files
    print("\n3. Ranking files...")
    ranked_files = file_selector.rank_files(
        query=query,
        search_results=search_results,
        temporal_refs=query_analysis.temporal_refs
    )
    
    print(f"   Ranked {len(ranked_files)} files:")
    for i, ranked_file in enumerate(ranked_files[:5], 1):
        print(f"   {i}. {ranked_file.file_metadata.name}")
        print(f"      Relevance: {ranked_file.relevance_score:.3f} "
              f"(semantic: {ranked_file.semantic_score:.3f}, "
              f"metadata: {ranked_file.metadata_score:.3f}, "
              f"preference: {ranked_file.preference_score:.3f})")
    
    # Step 4: Select file
    print("\n4. Selecting file...")
    file_selection = file_selector.select_file(ranked_files)
    
    if file_selection.requires_clarification:
        print(f"   Clarification needed (confidence: {file_selection.confidence:.3f})")
        print(f"   Top {len(file_selection.candidates)} candidates:")
        for i, candidate in enumerate(file_selection.candidates, 1):
            print(f"   {i}. {candidate.file_metadata.name} "
                  f"(score: {candidate.relevance_score:.3f})")
        
        # Simulate user selection
        print("\n   Simulating user selection: choosing option 1")
        selected_file = file_selector.handle_user_selection(
            query=query,
            candidates=file_selection.candidates,
            user_choice=0  # First option
        )
    else:
        print(f"   Auto-selected: {file_selection.selected_file.file_metadata.name}")
        print(f"   Confidence: {file_selection.confidence:.3f}")
        selected_file = file_selection.selected_file
    
    if not selected_file:
        print("\n   No file selected.")
        return
    
    # Step 5: Select sheet
    print("\n5. Selecting sheet...")
    sheet_selection = sheet_selector.select_sheet(
        file_id=selected_file.file_metadata.file_id,
        query=query,
        query_analysis=query_analysis,
        search_results=search_results
    )
    
    print(f"   Selected sheet: {sheet_selection.sheet_name}")
    print(f"   Relevance: {sheet_selection.relevance_score:.3f}")
    
    if sheet_selection.requires_clarification:
        print(f"   Note: Low confidence, may need clarification")
    
    # Step 6: Multi-sheet selection example
    print("\n6. Selecting multiple sheets (if applicable)...")
    multi_sheet_selection = sheet_selector.select_multiple_sheets(
        file_id=selected_file.file_metadata.file_id,
        query=query,
        query_analysis=query_analysis,
        search_results=search_results
    )
    
    print(f"   Selected {len(multi_sheet_selection.selected_sheets)} sheets")
    print(f"   Combination strategy: {multi_sheet_selection.combination_strategy}")
    
    for scored_sheet in multi_sheet_selection.selected_sheets:
        print(f"   - {scored_sheet.sheet_data.sheet_name} "
              f"(score: {scored_sheet.relevance_score:.3f})")
    
    # Step 7: Preference statistics
    print("\n7. Preference statistics...")
    stats = preference_manager.get_preference_statistics()
    print(f"   Total preferences: {stats.get('total_preferences', 0)}")
    print(f"   Recent preferences (7 days): {stats.get('recent_preferences', 0)}")
    
    print("\n" + "=" * 80)
    print("Example complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
