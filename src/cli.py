"""Command-line interface for the Google Drive Excel RAG System"""

import click
import logging
import webbrowser
import sys
import time
from datetime import datetime
from typing import Optional
from tqdm import tqdm

from src.config import get_config
from src.auth.authentication_service import AuthenticationService, AuthenticationStatus
from src.indexing.indexing_pipeline import IndexingPipeline
from src.indexing.indexing_orchestrator import IndexingState
from src.gdrive.connector import GoogleDriveConnector
from src.extraction.configurable_extractor import ConfigurableExtractor
from src.abstractions.embedding_service_factory import EmbeddingServiceFactory
from src.abstractions.vector_store_factory import VectorStoreFactory
from src.abstractions.cache_service_factory import CacheServiceFactory
from src.abstractions.llm_service_factory import LLMServiceFactory
from src.database.connection import DatabaseConnection, initialize_database
from src.query.query_engine import QueryEngine
from src.indexing.vector_storage import VectorStorageManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Google Drive Excel RAG System CLI"""
    pass


@cli.group()
def auth():
    """Authentication commands"""
    pass


@auth.command()
def login():
    """Initiate OAuth login flow"""
    try:
        # Load configuration
        config = get_config()
        auth_service = AuthenticationService(config.google_drive)
        
        # Check if already authenticated
        if auth_service.is_authenticated():
            click.echo("✓ Already authenticated!")
            click.echo("Use 'auth status' to see details or 'auth logout' to sign out.")
            return
        
        # Initiate OAuth flow
        click.echo("Initiating OAuth 2.0 authentication flow...")
        auth_url, state = auth_service.initiate_oauth_flow()
        
        # Open browser
        click.echo(f"\nOpening browser for authentication...")
        click.echo(f"If the browser doesn't open, visit this URL:\n{auth_url}\n")
        
        if webbrowser.open(auth_url):
            click.echo("✓ Browser opened successfully")
        else:
            click.echo("⚠ Could not open browser automatically")
        
        # Wait for user to complete OAuth flow
        click.echo("\nAfter authorizing, you'll receive an authorization code.")
        auth_code = click.prompt("Enter the authorization code", type=str)
        
        # Handle callback
        click.echo("\nProcessing authorization...")
        if auth_service.handle_oauth_callback(auth_code, state, state):
            click.echo("✓ Authentication successful!")
            click.echo("You can now use the indexing and query commands.")
        else:
            click.echo("✗ Authentication failed. Please try again.", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"✗ Error during authentication: {e}", err=True)
        logger.exception("Authentication error")
        sys.exit(1)


@auth.command()
def logout():
    """Logout and revoke access"""
    try:
        # Load configuration
        config = get_config()
        auth_service = AuthenticationService(config.google_drive)
        
        # Check if authenticated
        if not auth_service.is_authenticated():
            click.echo("Not currently authenticated.")
            return
        
        # Confirm logout
        if not click.confirm("Are you sure you want to logout and revoke access?"):
            click.echo("Logout cancelled.")
            return
        
        # Revoke access
        click.echo("Revoking access and clearing credentials...")
        if auth_service.revoke_access():
            click.echo("✓ Successfully logged out")
            click.echo("Your credentials have been removed.")
        else:
            click.echo("⚠ Logout completed but there may have been issues revoking the token.", err=True)
            click.echo("Your local credentials have been removed.")
            
    except Exception as e:
        click.echo(f"✗ Error during logout: {e}", err=True)
        logger.exception("Logout error")
        sys.exit(1)


@auth.command()
def status():
    """Check authentication status"""
    try:
        # Load configuration
        config = get_config()
        auth_service = AuthenticationService(config.google_drive)
        
        # Get authentication status
        auth_status = auth_service.get_authentication_status()
        
        click.echo("Authentication Status")
        click.echo("=" * 50)
        
        if auth_status == AuthenticationStatus.AUTHENTICATED:
            click.echo("Status: ✓ Authenticated")
            
            # Get credentials for more details
            credentials = auth_service.get_credentials()
            if credentials:
                # Show token expiry
                if credentials.expiry:
                    expiry_str = credentials.expiry.strftime("%Y-%m-%d %H:%M:%S")
                    now = datetime.utcnow()
                    
                    if credentials.expiry > now:
                        time_left = credentials.expiry - now
                        hours = time_left.total_seconds() / 3600
                        click.echo(f"Token Expiry: {expiry_str} UTC ({hours:.1f} hours remaining)")
                    else:
                        click.echo(f"Token Expiry: {expiry_str} UTC (expired)")
                else:
                    click.echo("Token Expiry: Not available")
                
                # Show scopes
                if credentials.scopes:
                    click.echo(f"Scopes: {', '.join(credentials.scopes)}")
                
                # Try to get user info
                try:
                    drive_service = auth_service.get_authenticated_client()
                    about = drive_service.about().get(fields="user").execute()
                    user = about.get('user', {})
                    if user:
                        click.echo(f"User: {user.get('displayName', 'Unknown')}")
                        click.echo(f"Email: {user.get('emailAddress', 'Unknown')}")
                except Exception as e:
                    logger.debug(f"Could not fetch user info: {e}")
                    
        elif auth_status == AuthenticationStatus.NOT_AUTHENTICATED:
            click.echo("Status: ✗ Not authenticated")
            click.echo("\nRun 'auth login' to authenticate with Google Drive.")
            
        elif auth_status == AuthenticationStatus.TOKEN_EXPIRED:
            click.echo("Status: ⚠ Token expired")
            click.echo("\nRun 'auth login' to re-authenticate.")
            
        elif auth_status == AuthenticationStatus.REFRESH_FAILED:
            click.echo("Status: ✗ Token refresh failed")
            click.echo("\nRun 'auth login' to re-authenticate.")
        
        click.echo("=" * 50)
        
    except Exception as e:
        click.echo(f"✗ Error checking authentication status: {e}", err=True)
        logger.exception("Status check error")
        sys.exit(1)


@cli.group()
def index():
    """Indexing commands"""
    pass


@index.command()
@click.option('--watch', is_flag=True, help='Continuously monitor progress')
def full(watch: bool):
    """Start full indexing of all files"""
    try:
        # Load configuration
        config = get_config()
        
        # Check authentication
        auth_service = AuthenticationService(config.google_drive)
        if not auth_service.is_authenticated():
            click.echo("✗ Not authenticated. Run 'auth login' first.", err=True)
            sys.exit(1)
        
        # Create indexing pipeline
        click.echo("Initializing indexing pipeline...")
        pipeline = _create_indexing_pipeline(config, auth_service)
        
        # Start full indexing
        click.echo("Starting full indexing of all files...")
        click.echo("This may take a while depending on the number of files.\n")
        
        if watch:
            # Monitor progress with updates
            _monitor_indexing_progress(pipeline)
        else:
            # Simple progress bar
            with tqdm(desc="Indexing", unit="files") as pbar:
                last_processed = 0
                while True:
                    progress = pipeline.get_progress()
                    
                    # Update progress bar
                    current_processed = progress.files_processed
                    if current_processed > last_processed:
                        pbar.update(current_processed - last_processed)
                        last_processed = current_processed
                    
                    # Check if done
                    if progress.state in [IndexingState.COMPLETED, IndexingState.FAILED, IndexingState.STOPPED]:
                        break
                    
                    time.sleep(1)
        
        # Get final report
        progress = pipeline.get_progress()
        
        click.echo("\n" + "=" * 60)
        click.echo("Indexing Complete")
        click.echo("=" * 60)
        click.echo(f"Files Processed: {progress.files_processed}")
        click.echo(f"Files Failed: {progress.files_failed}")
        click.echo(f"Files Skipped: {progress.files_skipped}")
        click.echo(f"Duration: {progress.duration_seconds:.2f} seconds")
        
        # Get statistics
        stats = pipeline.get_statistics()
        if 'embedding_cost' in stats:
            cost = stats['embedding_cost']
            click.echo(f"\nEmbedding Cost: ${cost.get('total_cost', 0):.4f}")
            click.echo(f"Total Tokens: {cost.get('total_tokens', 0):,}")
        
        click.echo("=" * 60)
        
    except Exception as e:
        click.echo(f"✗ Error during indexing: {e}", err=True)
        logger.exception("Indexing error")
        sys.exit(1)


@index.command()
@click.option('--watch', is_flag=True, help='Continuously monitor progress')
def incremental(watch: bool):
    """Start incremental indexing of changed files"""
    try:
        # Load configuration
        config = get_config()
        
        # Check authentication
        auth_service = AuthenticationService(config.google_drive)
        if not auth_service.is_authenticated():
            click.echo("✗ Not authenticated. Run 'auth login' first.", err=True)
            sys.exit(1)
        
        # Create indexing pipeline
        click.echo("Initializing indexing pipeline...")
        pipeline = _create_indexing_pipeline(config, auth_service)
        
        # Start incremental indexing
        click.echo("Starting incremental indexing of changed files...")
        click.echo("Checking for file changes...\n")
        
        if watch:
            # Monitor progress with updates
            _monitor_indexing_progress(pipeline)
        else:
            # Simple progress bar
            with tqdm(desc="Indexing", unit="files") as pbar:
                last_processed = 0
                while True:
                    progress = pipeline.get_progress()
                    
                    # Update progress bar
                    current_processed = progress.files_processed
                    if current_processed > last_processed:
                        pbar.update(current_processed - last_processed)
                        last_processed = current_processed
                    
                    # Check if done
                    if progress.state in [IndexingState.COMPLETED, IndexingState.FAILED, IndexingState.STOPPED]:
                        break
                    
                    time.sleep(1)
        
        # Get final report
        progress = pipeline.get_progress()
        
        click.echo("\n" + "=" * 60)
        click.echo("Incremental Indexing Complete")
        click.echo("=" * 60)
        click.echo(f"Files Processed: {progress.files_processed}")
        click.echo(f"Files Failed: {progress.files_failed}")
        click.echo(f"Files Skipped: {progress.files_skipped}")
        click.echo(f"Duration: {progress.duration_seconds:.2f} seconds")
        
        # Get statistics
        stats = pipeline.get_statistics()
        if 'embedding_cost' in stats:
            cost = stats['embedding_cost']
            click.echo(f"\nEmbedding Cost: ${cost.get('total_cost', 0):.4f}")
            click.echo(f"Total Tokens: {cost.get('total_tokens', 0):,}")
        
        click.echo("=" * 60)
        
    except Exception as e:
        click.echo(f"✗ Error during incremental indexing: {e}", err=True)
        logger.exception("Incremental indexing error")
        sys.exit(1)


@index.command()
def status():
    """Show indexing status"""
    try:
        # Load configuration
        config = get_config()
        
        # Check authentication
        auth_service = AuthenticationService(config.google_drive)
        if not auth_service.is_authenticated():
            click.echo("✗ Not authenticated. Run 'auth login' first.", err=True)
            sys.exit(1)
        
        # Create indexing pipeline
        pipeline = _create_indexing_pipeline(config, auth_service)
        
        # Get current progress
        progress = pipeline.get_progress()
        
        click.echo("Indexing Status")
        click.echo("=" * 60)
        click.echo(f"State: {progress.state.value}")
        click.echo(f"Progress: {progress.progress_percentage:.1f}%")
        click.echo(f"Files Processed: {progress.files_processed}")
        click.echo(f"Files Failed: {progress.files_failed}")
        click.echo(f"Files Skipped: {progress.files_skipped}")
        
        if progress.current_file:
            click.echo(f"Current File: {progress.current_file}")
        
        click.echo(f"Duration: {progress.duration_seconds:.2f} seconds")
        
        if progress.estimated_time_remaining:
            click.echo(f"Estimated Time Remaining: {progress.estimated_time_remaining:.2f} seconds")
        
        click.echo("=" * 60)
        
    except Exception as e:
        click.echo(f"✗ Error getting indexing status: {e}", err=True)
        logger.exception("Status check error")
        sys.exit(1)


@index.command()
def report():
    """Show detailed indexing report with statistics"""
    try:
        # Load configuration
        config = get_config()
        
        # Check authentication
        auth_service = AuthenticationService(config.google_drive)
        if not auth_service.is_authenticated():
            click.echo("✗ Not authenticated. Run 'auth login' first.", err=True)
            sys.exit(1)
        
        # Create indexing pipeline
        pipeline = _create_indexing_pipeline(config, auth_service)
        
        # Get comprehensive statistics
        stats = pipeline.get_statistics()
        
        click.echo("Indexing Report")
        click.echo("=" * 60)
        
        # Metadata statistics
        if 'metadata' in stats:
            meta = stats['metadata']
            click.echo("\nMetadata Storage:")
            click.echo(f"  Total Files: {meta.get('total_files', 0)}")
            click.echo(f"  Total Sheets: {meta.get('total_sheets', 0)}")
            click.echo(f"  Total Pivot Tables: {meta.get('total_pivot_tables', 0)}")
            click.echo(f"  Total Charts: {meta.get('total_charts', 0)}")
        
        # Vector store statistics
        if 'vector_store' in stats:
            vector = stats['vector_store']
            click.echo("\nVector Store:")
            for collection, count in vector.items():
                click.echo(f"  {collection}: {count} embeddings")
        
        # Embedding cost
        if 'embedding_cost' in stats:
            cost = stats['embedding_cost']
            click.echo("\nEmbedding Cost:")
            click.echo(f"  Total Cost: ${cost.get('total_cost', 0):.4f}")
            click.echo(f"  Total Tokens: {cost.get('total_tokens', 0):,}")
            click.echo(f"  Total Requests: {cost.get('total_requests', 0)}")
        
        # Current progress
        if 'current_progress' in stats:
            prog = stats['current_progress']
            click.echo("\nCurrent Progress:")
            click.echo(f"  State: {prog.get('state', 'unknown')}")
            click.echo(f"  Progress: {prog.get('progress_percentage', 0):.1f}%")
            click.echo(f"  Files Processed: {prog.get('files_processed', 0)}")
            click.echo(f"  Files Failed: {prog.get('files_failed', 0)}")
            click.echo(f"  Files Skipped: {prog.get('files_skipped', 0)}")
        
        click.echo("=" * 60)
        
    except Exception as e:
        click.echo(f"✗ Error generating report: {e}", err=True)
        logger.exception("Report generation error")
        sys.exit(1)


@cli.group()
def query():
    """Query commands"""
    pass


@query.command()
@click.argument('question')
@click.option('--session', default=None, help='Session ID for follow-up questions')
def ask(question: str, session: Optional[str]):
    """Submit a natural language query"""
    try:
        # Load configuration
        config = get_config()
        
        # Check authentication
        auth_service = AuthenticationService(config.google_drive)
        if not auth_service.is_authenticated():
            click.echo("✗ Not authenticated. Run 'auth login' first.", err=True)
            sys.exit(1)
        
        # Create query engine
        query_engine = _create_query_engine(config)
        
        # Process query
        click.echo(f"\nProcessing query: {question}\n")
        
        result = query_engine.process_query(
            query=question,
            session_id=session
        )
        
        # Display results
        click.echo("=" * 70)
        
        # Check if clarification needed
        if result.clarification_request:
            click.echo("⚠ Clarification Needed\n")
            click.echo(result.clarification_request.question)
            click.echo("\nOptions:")
            for i, option in enumerate(result.clarification_request.options, 1):
                click.echo(f"  {i}. {option}")
            
            # Get user selection
            choice = click.prompt(
                "\nSelect an option (number)",
                type=click.IntRange(1, len(result.clarification_request.options))
            )
            
            # Process with selected option
            selected = result.clarification_request.options[choice - 1]
            click.echo(f"\nProcessing with selection: {selected}\n")
            
            # Re-query with clarification
            # Note: This is a simplified version. Full implementation would
            # handle clarification responses properly
            click.echo("Clarification handling is simplified in CLI.")
            click.echo("For full clarification support, use the API.")
            
        else:
            # Display answer
            click.echo("Answer:")
            click.echo("-" * 70)
            click.echo(result.answer)
            click.echo("-" * 70)
            
            # Display sources
            if result.sources:
                click.echo("\nSources:")
                for i, source in enumerate(result.sources, 1):
                    click.echo(f"  [{i}] {source}")
            
            # Display confidence
            if result.confidence is not None:
                confidence_bar = "█" * int(result.confidence / 10)
                click.echo(f"\nConfidence: {result.confidence:.1f}% {confidence_bar}")
            
            # Display session info
            if result.session_id:
                click.echo(f"\nSession ID: {result.session_id}")
                click.echo("Use --session flag with this ID for follow-up questions")
        
        click.echo("=" * 70)
        
    except Exception as e:
        click.echo(f"✗ Error processing query: {e}", err=True)
        logger.exception("Query processing error")
        sys.exit(1)


@query.command()
@click.option('--session', required=True, help='Session ID')
@click.option('--limit', default=10, help='Number of queries to show')
def history(session: str, limit: int):
    """Show recent queries and answers"""
    try:
        # Load configuration
        config = get_config()
        
        # Create query engine
        query_engine = _create_query_engine(config)
        
        # Get query history
        queries = query_engine.get_query_history(session, limit)
        
        if not queries:
            click.echo(f"No query history found for session: {session}")
            return
        
        click.echo(f"Query History (Session: {session})")
        click.echo("=" * 70)
        
        for i, q in enumerate(queries, 1):
            click.echo(f"{i}. {q}")
        
        click.echo("=" * 70)
        
    except Exception as e:
        click.echo(f"✗ Error retrieving query history: {e}", err=True)
        logger.exception("Query history error")
        sys.exit(1)


@query.command()
@click.option('--session', required=True, help='Session ID')
def clear(session: str):
    """Clear query history"""
    try:
        # Load configuration
        config = get_config()
        
        # Create query engine
        query_engine = _create_query_engine(config)
        
        # Confirm
        if not click.confirm(f"Clear query history for session {session}?"):
            click.echo("Cancelled.")
            return
        
        # Clear session
        if query_engine.clear_session(session):
            click.echo(f"✓ Query history cleared for session: {session}")
        else:
            click.echo(f"✗ Failed to clear query history for session: {session}", err=True)
        
    except Exception as e:
        click.echo(f"✗ Error clearing query history: {e}", err=True)
        logger.exception("Query clear error")
        sys.exit(1)


@cli.group()
def config():
    """Configuration commands"""
    pass


@config.command()
def show():
    """Display current configuration"""
    try:
        cfg = get_config()
        click.echo("Current Configuration:")
        click.echo(f"  Environment: {cfg.env}")
        click.echo(f"  Log Level: {cfg.log_level}")
        click.echo(f"  Vector Store: {cfg.vector_store.provider}")
        click.echo(f"  Embedding Provider: {cfg.embedding.provider}")
        click.echo(f"  LLM Provider: {cfg.llm.provider}")
        click.echo(f"  Database Path: {cfg.database.db_path}")
        
        # Validate configuration
        errors = cfg.validate()
        if errors:
            click.echo("\nConfiguration Warnings:")
            for error in errors:
                click.echo(f"  - {error}")
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)


@config.command()
@click.argument('key')
@click.argument('value')
def set(key: str, value: str):
    """Update configuration value"""
    click.echo(f"Setting {key} = {value}")
    click.echo("Note: Update the .env file to persist changes")
    # Configuration is loaded from environment variables


@config.command()
def validate():
    """Validate current configuration"""
    try:
        cfg = get_config()
        errors = cfg.validate()
        
        if not errors:
            click.echo("✓ Configuration is valid")
        else:
            click.echo("Configuration validation failed:")
            for error in errors:
                click.echo(f"  ✗ {error}")
    except Exception as e:
        click.echo(f"Error validating configuration: {e}", err=True)


def _create_query_engine(config) -> QueryEngine:
    """Helper function to create query engine with all dependencies"""
    # Create LLM service
    llm_service = LLMServiceFactory.create(
        config.llm.provider,
        config.llm.config
    )
    
    # Create embedding service
    embedding_service = EmbeddingServiceFactory.create(
        config.embedding.provider,
        config.embedding.config
    )
    
    # Create cache service
    cache_service = CacheServiceFactory.create(
        config.cache.provider,
        config.cache.config
    )
    
    # Create vector store
    vector_store = VectorStoreFactory.create(
        config.vector_store.provider,
        config.vector_store.config
    )
    
    # Create vector storage manager
    vector_storage = VectorStorageManager(vector_store)
    
    # Create query engine
    query_engine = QueryEngine(
        llm_service=llm_service,
        embedding_service=embedding_service,
        cache_service=cache_service,
        vector_storage=vector_storage
    )
    
    return query_engine


def _create_indexing_pipeline(config, auth_service: AuthenticationService) -> IndexingPipeline:
    """Helper function to create indexing pipeline with all dependencies"""
    # Create Google Drive connector
    drive_client = auth_service.get_authenticated_client()
    gdrive_connector = GoogleDriveConnector(drive_client, config.google_drive)
    
    # Create content extractor
    content_extractor = ConfigurableExtractor(config.extraction)
    
    # Create embedding service
    embedding_service = EmbeddingServiceFactory.create(
        config.embedding.provider,
        config.embedding.config
    )
    
    # Create vector store
    vector_store = VectorStoreFactory.create(
        config.vector_store.provider,
        config.vector_store.config
    )
    
    # Create cache service
    cache_service = CacheServiceFactory.create(
        config.cache.provider,
        config.cache.config
    )
    
    # Get database connection
    db_connection = initialize_database(config.database.db_path)
    
    # Create pipeline
    pipeline = IndexingPipeline(
        gdrive_connector=gdrive_connector,
        content_extractor=content_extractor,
        embedding_service=embedding_service,
        vector_store=vector_store,
        db_connection=db_connection,
        cache_service=cache_service,
        max_workers=5,
        batch_size=100
    )
    
    return pipeline


def _monitor_indexing_progress(pipeline: IndexingPipeline):
    """Monitor indexing progress with continuous updates"""
    click.echo("Monitoring indexing progress (Ctrl+C to stop monitoring)...\n")
    
    try:
        last_processed = 0
        last_state = None
        
        while True:
            progress = pipeline.get_progress()
            
            # Check if state changed
            if progress.state != last_state:
                click.echo(f"\nState: {progress.state.value}")
                last_state = progress.state
            
            # Show progress update
            if progress.files_processed > last_processed:
                click.echo(
                    f"Progress: {progress.progress_percentage:.1f}% | "
                    f"Processed: {progress.files_processed} | "
                    f"Failed: {progress.files_failed} | "
                    f"Skipped: {progress.files_skipped}"
                )
                if progress.current_file:
                    click.echo(f"  Current: {progress.current_file}")
                last_processed = progress.files_processed
            
            # Check if done
            if progress.state in [IndexingState.COMPLETED, IndexingState.FAILED, IndexingState.STOPPED]:
                break
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        click.echo("\n\nStopped monitoring. Indexing continues in background.")


if __name__ == "__main__":
    cli()
