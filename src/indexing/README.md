# Indexing Pipeline

This module provides a comprehensive indexing pipeline for Excel files from Google Drive. It orchestrates the entire process from file discovery to embedding generation and storage.

## Components

### IndexingPipeline

The main entry point for indexing operations. It coordinates all components and provides a simple interface for:

- **Full indexing**: Index all Excel files from Google Drive
- **Incremental indexing**: Index only new or modified files
- **Progress tracking**: Monitor indexing progress in real-time
- **Cost tracking**: Track embedding generation costs for API-based services

```python
from src.indexing import IndexingPipeline

pipeline = IndexingPipeline(
    gdrive_connector=gdrive_connector,
    content_extractor=content_extractor,
    embedding_service=embedding_service,
    vector_store=vector_store,
    db_connection=db_connection,
    cache_service=cache_service,  # Optional
    max_workers=5,
    batch_size=100,
    cost_per_token=0.00002
)

# Full indexing
report = pipeline.full_index()

# Incremental indexing
report = pipeline.incremental_index()

# Get progress
progress = pipeline.get_progress()
print(f"Progress: {progress.progress_percentage:.1f}%")

# Get statistics
stats = pipeline.get_statistics()
```

### IndexingOrchestrator

Manages the indexing workflow with support for:

- **Parallel processing**: Process multiple files concurrently (configurable workers)
- **State tracking**: Track files as pending, indexed, failed, or deleted
- **Pause/resume**: Control indexing execution
- **Change detection**: Use MD5 checksums to detect file changes

```python
from src.indexing import IndexingOrchestrator

orchestrator = IndexingOrchestrator(
    gdrive_connector=gdrive_connector,
    content_extractor=content_extractor,
    db_connection=db_connection,
    max_workers=5
)

# Start indexing
report = orchestrator.full_index()

# Pause indexing
orchestrator.pause()

# Resume indexing
orchestrator.resume()

# Stop indexing
orchestrator.stop()
```

### EmbeddingGenerator

Generates embeddings for Excel content with:

- **Batching**: Process texts in configurable batches (default: 100)
- **Caching**: Cache embeddings to avoid regeneration
- **Retry logic**: Handle API errors with exponential backoff
- **Cost tracking**: Track tokens and estimated costs

```python
from src.indexing import EmbeddingGenerator

generator = EmbeddingGenerator(
    embedding_service=embedding_service,
    cache_service=cache_service,  # Optional
    batch_size=100,
    max_retries=3,
    cost_per_token=0.00002
)

# Generate embeddings for a workbook
result = generator.generate_workbook_embeddings(workbook_data)

# Get cost summary
cost = generator.get_cost_summary()
print(f"Cost: ${cost['estimated_cost_usd']:.4f}")
```

### VectorStorageManager

Manages storage of embeddings in vector databases:

- **Separate collections**: Sheets, pivot tables, and charts in separate collections
- **Rich metadata**: Store metadata for filtering and ranking
- **Duplicate handling**: Update existing embeddings instead of duplicating
- **Search capabilities**: Search across different content types

```python
from src.indexing import VectorStorageManager

storage = VectorStorageManager(vector_store=vector_store)

# Initialize collections
storage.initialize_collections(embedding_dimension=1536)

# Store embeddings
storage.store_workbook_embeddings(workbook_data, embedding_result)

# Search
results = storage.search_sheets(query_embedding, top_k=10)
```

### MetadataStorageManager

Manages metadata storage in SQLite:

- **File metadata**: Store file information with MD5 checksums
- **Sheet structure**: Store sheet headers, data types, and statistics
- **Pivot tables**: Store pivot table definitions
- **Charts**: Store chart metadata
- **Statistics**: Get comprehensive indexing statistics

```python
from src.indexing import MetadataStorageManager

metadata = MetadataStorageManager(db_connection=db_connection)

# Store workbook metadata
metadata.store_workbook_metadata(workbook_data)

# Get statistics
stats = metadata.get_indexing_statistics()
print(f"Total sheets: {stats['total_sheets']}")
```

## Indexing Workflow

The complete indexing workflow:

1. **Discovery**: List all Excel files from Google Drive
2. **Change Detection**: Compare MD5 checksums to identify changed files
3. **Download**: Download file content from Google Drive
4. **Extraction**: Parse Excel files and extract structured data
5. **Embedding Generation**: Generate embeddings for content (batched)
6. **Vector Storage**: Store embeddings in vector database
7. **Metadata Storage**: Store metadata in SQLite database
8. **Progress Tracking**: Update progress and generate reports

## Embedding Strategy

The system generates multiple embeddings per sheet:

1. **Sheet Overview**: File name + sheet name + headers + summary + sample data
2. **Column Summaries**: Statistics and sample values for numerical columns
3. **Pivot Tables**: Natural language descriptions of pivot table structure
4. **Charts**: Descriptions of chart type, title, and data context

This multi-embedding approach enables:
- Better semantic search across different content types
- Targeted queries for specific data types
- Improved relevance ranking

## Collections

Three separate vector store collections:

### excel_sheets
- Sheet overviews and column summaries
- Metadata: file_id, file_name, sheet_name, row_count, has_dates, has_numbers, etc.

### excel_pivots
- Pivot table descriptions
- Metadata: file_id, sheet_name, pivot_name, row_fields, data_fields

### excel_charts
- Chart descriptions
- Metadata: file_id, sheet_name, chart_name, chart_type, chart_title

## Progress Tracking

Real-time progress tracking with:

- **State**: idle, running, paused, completed, failed
- **Counts**: files processed, failed, skipped
- **Progress percentage**: Calculated from total files
- **Duration**: Elapsed time
- **Current file**: Currently processing file
- **Errors**: List of error messages

```python
progress = pipeline.get_progress()

print(f"State: {progress.state.value}")
print(f"Progress: {progress.progress_percentage:.1f}%")
print(f"Processed: {progress.files_processed}/{progress.total_files}")
print(f"Failed: {progress.files_failed}")
print(f"Skipped: {progress.files_skipped}")
print(f"Duration: {progress.duration_seconds:.2f}s")
```

## Cost Tracking

Track embedding generation costs:

- **Total embeddings**: Number of embeddings generated
- **Total tokens**: Approximate token count
- **Total requests**: Number of API requests
- **Estimated cost**: Cost in USD (configurable per-token rate)

```python
cost = pipeline.get_statistics()['embedding_cost']

print(f"Provider: {cost['provider']}")
print(f"Model: {cost['model']}")
print(f"Embeddings: {cost['total_embeddings']}")
print(f"Tokens: {cost['total_tokens']}")
print(f"Cost: ${cost['estimated_cost_usd']:.4f}")
```

## Caching

Optional caching for embeddings:

- **Cache key**: Based on text ID and content hash (MD5)
- **TTL**: 30 days (configurable)
- **Benefits**: Avoid regenerating embeddings for unchanged content
- **Providers**: Memory cache or Redis

```python
from src.abstractions import CacheServiceFactory

cache_service = CacheServiceFactory.create(
    provider="redis",
    config={"host": "localhost", "port": 6379}
)

pipeline = IndexingPipeline(
    # ... other params
    cache_service=cache_service
)
```

## Error Handling

Robust error handling:

- **File-level errors**: Skip failed files and continue processing
- **API errors**: Retry with exponential backoff
- **Rate limits**: Automatic retry with delays
- **Corrupted files**: Log error and mark as failed
- **Network errors**: Retry with backoff

All errors are logged and included in the indexing report.

## Performance

Optimizations for large-scale indexing:

- **Parallel processing**: Process up to 5 files concurrently (configurable)
- **Batch embeddings**: Generate embeddings in batches of 100
- **Caching**: Avoid regenerating embeddings for unchanged content
- **Incremental indexing**: Only process changed files
- **Streaming**: Stream large files instead of loading entirely

## Example Usage

See `examples/indexing_usage.py` for complete examples including:

1. Full indexing with progress tracking
2. Incremental indexing
3. Progress monitoring
4. Statistics and cost reporting
5. Error handling

## Configuration

Key configuration options:

```python
# Indexing pipeline
max_workers = 5          # Concurrent file processing
batch_size = 100         # Embedding batch size
cost_per_token = 0.00002 # Cost per token (USD)

# Retry logic
max_retries = 3          # Maximum retry attempts
retry_delay = 1.0        # Initial retry delay (seconds)

# Caching
cache_ttl = 2592000      # Cache TTL (30 days)
```

## Database Schema

The indexing pipeline uses the following tables:

- **files**: File metadata with MD5 checksums and status
- **sheets**: Sheet structure and statistics
- **pivot_tables**: Pivot table definitions
- **charts**: Chart metadata

See `src/database/schema.py` for complete schema definitions.

## LLM Summarization Support

**Current Limitation**: The indexing pipeline currently uses synchronous extraction (`extract_workbook_sync`) which does not include LLM-generated sheet summaries. This is because the pipeline uses ThreadPoolExecutor for parallel processing, which doesn't support async operations.

**Workaround**: Sheet summaries are still generated using the basic rule-based approach in the ContentExtractor. The `llm_summary` field in SheetData will be None.

**Future Enhancement**: An async version of the indexing pipeline will be added to support LLM summarization during indexing. This will use asyncio for concurrent processing and enable the full `ConfigurableExtractor` capabilities including:
- LLM-generated semantic summaries for sheets
- Smart extraction with automatic fallback
- Gemini and LlamaParse integration

## Future Enhancements

Potential improvements:

1. **Async indexing pipeline**: Support async extraction with LLM summarization
2. **Streaming embeddings**: Generate embeddings as files are processed
3. **Priority queue**: Prioritize certain files for indexing
4. **Webhook support**: Real-time indexing on file changes
5. **Distributed processing**: Scale across multiple workers
6. **Advanced caching**: Cache at multiple levels (embeddings, extractions)
7. **Compression**: Compress embeddings for storage efficiency
