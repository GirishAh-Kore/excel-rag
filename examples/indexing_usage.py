"""
Example: Using the Indexing Pipeline

This example demonstrates how to use the indexing pipeline to index Excel files
from Google Drive, including full indexing, incremental indexing, and progress tracking.
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import AppConfig
from src.auth.authentication_service import AuthenticationService
from src.gdrive.connector import GoogleDriveConnector
from src.extraction.configurable_extractor import ConfigurableExtractor
from src.abstractions.embedding_service_factory import EmbeddingServiceFactory
from src.abstractions.vector_store_factory import VectorStoreFactory
from src.abstractions.cache_service_factory import CacheServiceFactory
from src.database.connection import DatabaseConnection
from src.indexing.indexing_pipeline import IndexingPipeline


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main example function"""
    
    # Load configuration
    config = AppConfig.from_env()
    
    # Initialize authentication
    auth_service = AuthenticationService(
        client_id=config.google_client_id,
        client_secret=config.google_client_secret,
        redirect_uri=config.google_redirect_uri
    )
    
    # Check if authenticated
    if not auth_service.is_authenticated():
        logger.error("Not authenticated. Please run auth_usage.py first.")
        return
    
    # Initialize Google Drive connector
    gdrive_connector = GoogleDriveConnector(auth_service)
    
    # Initialize content extractor
    content_extractor = ConfigurableExtractor(config.extraction)
    
    # Initialize embedding service
    embedding_service = EmbeddingServiceFactory.create(
        provider=config.embedding.provider,
        config=config.embedding.config
    )
    
    # Initialize vector store
    vector_store = VectorStoreFactory.create(
        store_type=config.vector_store.provider,
        config=config.vector_store.config
    )
    
    # Initialize cache service (optional)
    cache_service = None
    if config.cache:
        try:
            cache_service = CacheServiceFactory.create(
                provider=config.cache.provider,
                config=config.cache.config
            )
            logger.info("Cache service initialized")
        except Exception as e:
            logger.warning(f"Cache service not available: {e}")
    
    # Initialize database connection
    db_connection = DatabaseConnection(config.database_path)
    
    # Initialize indexing pipeline
    pipeline = IndexingPipeline(
        gdrive_connector=gdrive_connector,
        content_extractor=content_extractor,
        embedding_service=embedding_service,
        vector_store=vector_store,
        db_connection=db_connection,
        cache_service=cache_service,
        max_workers=5,
        batch_size=100,
        cost_per_token=0.00002  # OpenAI text-embedding-3-small cost
    )
    
    # Example 1: Full indexing
    logger.info("=" * 60)
    logger.info("Example 1: Full Indexing")
    logger.info("=" * 60)
    
    try:
        # Start full indexing
        logger.info("Starting full indexing...")
        
        # Monitor progress in a separate thread (simplified for example)
        report = pipeline.full_index()
        
        # Display results
        logger.info("\nIndexing Report:")
        logger.info(f"  Total files: {report.total_files}")
        logger.info(f"  Files processed: {report.files_processed}")
        logger.info(f"  Files failed: {report.files_failed}")
        logger.info(f"  Files skipped: {report.files_skipped}")
        logger.info(f"  Total sheets: {report.total_sheets}")
        logger.info(f"  Duration: {report.duration_seconds:.2f} seconds")
        
        if report.errors:
            logger.warning(f"\nErrors ({len(report.errors)}):")
            for error in report.errors[:5]:  # Show first 5 errors
                logger.warning(f"  - {error}")
        
        # Get statistics
        stats = pipeline.get_statistics()
        logger.info("\nStatistics:")
        logger.info(f"  Embedding cost: ${stats['embedding_cost']['estimated_cost_usd']:.4f}")
        logger.info(f"  Total embeddings: {stats['embedding_cost']['total_embeddings']}")
        logger.info(f"  Total tokens: {stats['embedding_cost']['total_tokens']}")
        
    except Exception as e:
        logger.error(f"Full indexing failed: {e}", exc_info=True)
    
    # Example 2: Incremental indexing
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Incremental Indexing")
    logger.info("=" * 60)
    
    try:
        # Wait a bit to simulate time passing
        logger.info("Waiting 5 seconds before incremental indexing...")
        time.sleep(5)
        
        # Start incremental indexing
        logger.info("Starting incremental indexing...")
        report = pipeline.incremental_index()
        
        # Display results
        logger.info("\nIncremental Indexing Report:")
        logger.info(f"  Files processed: {report.files_processed}")
        logger.info(f"  Files failed: {report.files_failed}")
        logger.info(f"  Files skipped: {report.files_skipped}")
        logger.info(f"  Duration: {report.duration_seconds:.2f} seconds")
        
    except Exception as e:
        logger.error(f"Incremental indexing failed: {e}", exc_info=True)
    
    # Example 3: Progress tracking
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Progress Tracking")
    logger.info("=" * 60)
    
    # Get current progress
    progress = pipeline.get_progress()
    logger.info(f"Current state: {progress.state.value}")
    logger.info(f"Progress: {progress.progress_percentage:.1f}%")
    logger.info(f"Files processed: {progress.files_processed}")
    logger.info(f"Files failed: {progress.files_failed}")
    logger.info(f"Files skipped: {progress.files_skipped}")
    
    # Example 4: Get comprehensive statistics
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Comprehensive Statistics")
    logger.info("=" * 60)
    
    stats = pipeline.get_statistics()
    
    logger.info("\nMetadata Statistics:")
    metadata = stats['metadata']
    logger.info(f"  Total files: {metadata.get('total_files', 0)}")
    logger.info(f"  Indexed files: {metadata.get('indexed_files', 0)}")
    logger.info(f"  Failed files: {metadata.get('failed_files', 0)}")
    logger.info(f"  Total sheets: {metadata.get('total_sheets', 0)}")
    logger.info(f"  Total pivot tables: {metadata.get('total_pivot_tables', 0)}")
    logger.info(f"  Total charts: {metadata.get('total_charts', 0)}")
    logger.info(f"  Last indexed: {metadata.get('last_indexed_at', 'N/A')}")
    
    logger.info("\nEmbedding Cost:")
    cost = stats['embedding_cost']
    logger.info(f"  Provider: {cost['provider']}")
    logger.info(f"  Model: {cost['model']}")
    logger.info(f"  Total embeddings: {cost['total_embeddings']}")
    logger.info(f"  Total tokens: {cost['total_tokens']}")
    logger.info(f"  Estimated cost: ${cost['estimated_cost_usd']:.4f}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Indexing examples completed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
