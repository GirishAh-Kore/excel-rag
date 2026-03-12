# Query Processing Module

This module implements the complete query processing pipeline for the Google Drive Excel RAG system. It analyzes natural language queries, performs semantic search, manages conversation context, handles clarifications, and orchestrates the entire query workflow.

## Components

### 1. QueryAnalyzer (`query_analyzer.py`)

Analyzes user queries to extract structured information:
- **Entities**: Key concepts mentioned (e.g., "expenses", "revenue")
- **Intent**: What the user wants to do (retrieve_value, compare, explain_formula, etc.)
- **Temporal References**: Dates, months, quarters parsed from the query
- **Comparison Detection**: Identifies if query requires comparing multiple files
- **Data Types**: What types of data are requested (numbers, dates, formulas, charts, pivots)
- **File Hints**: File names or paths mentioned in the query

**Key Features:**
- Uses LLM for deep semantic understanding
- Regex-based temporal parsing with dateparser
- Keyword-based comparison detection
- Confidence scoring

### 2. SemanticSearcher (`semantic_searcher.py`)

Performs semantic search across indexed Excel files:
- **Multi-Collection Search**: Searches sheets, pivot tables, and charts
- **Query Embedding**: Generates embeddings for semantic similarity
- **Metadata Filtering**: Applies filters based on query analysis
- **Comparison Mode**: Returns diverse file candidates for comparisons
- **Result Ranking**: Sorts by similarity score

**Key Features:**
- Pluggable embedding service
- Intelligent collection selection based on query intent
- Deduplication for comparison queries
- Rich result metadata

### 3. ConversationManager (`conversation_manager.py`)

Manages conversation state across multiple queries:
- **Session Management**: Creates and tracks conversation sessions
- **Context Storage**: Stores queries, selected files, and sheets
- **Session Timeout**: 30-minute TTL using cache service
- **Reference Resolution**: Resolves ambiguous references in follow-up questions
- **Query History**: Maintains last 10 queries per session

**Key Features:**
- Cache-based storage (Redis or in-memory)
- Automatic session expiration
- Follow-up question detection
- Session statistics

### 4. ClarificationGenerator (`clarification_generator.py`)

Generates clarifying questions for ambiguous queries:
- **Ambiguity Detection**: Low confidence or similar scores
- **Question Generation**: Uses LLM to create natural questions
- **Option Presentation**: Formats top candidates as choices
- **Response Handling**: Parses user selections (ID, label, or number)

**Key Features:**
- Multiple clarification types (file, sheet, intent)
- Configurable thresholds (70% confidence, 5% score similarity)
- Natural language question generation
- Flexible response parsing

### 5. QueryEngine (`query_engine.py`)

Main orchestrator for the complete query processing pipeline:
- **Pipeline Orchestration**: Coordinates all components
- **Error Handling**: Comprehensive error recovery
- **Performance Tracking**: Measures processing time
- **Context Integration**: Uses conversation context for follow-ups

**Pipeline Stages:**
1. Analyze query (QueryAnalyzer)
2. Semantic search (SemanticSearcher)
3. Check clarification (ClarificationGenerator)
4. Select files/sheets (FileSelector/SheetSelector - tasks 9-10)
5. Retrieve data (data retrieval components)
6. Generate answer (AnswerGenerator - task 11)
7. Handle comparisons (ComparisonEngine - task 10)

## Usage Example

```python
from src.config import AppConfig
from src.abstractions.llm_service_factory import LLMServiceFactory
from src.abstractions.embedding_service_factory import EmbeddingServiceFactory
from src.abstractions.cache_service_factory import CacheServiceFactory
from src.abstractions.vector_store_factory import VectorStoreFactory
from src.indexing.vector_storage import VectorStorageManager
from src.query import QueryEngine

# Load configuration
config = AppConfig.from_env()

# Create services
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

# Process a query
result = query_engine.process_query(
    query="What were the total expenses in January 2024?"
)

print(f"Answer: {result.answer}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Processing time: {result.processing_time_ms}ms")

# Handle clarification if needed
if result.clarification_needed:
    print(f"Clarification needed: {result.clarifying_questions[0]}")
    # User provides response...
    # clarification_result = query_engine.handle_clarification_response(...)

# Follow-up query in same session
follow_up = query_engine.process_query(
    query="What about February?",
    session_id=result.session_id  # Reuse session
)
```

## Individual Component Usage

### QueryAnalyzer

```python
from src.query import QueryAnalyzer

analyzer = QueryAnalyzer(llm_service)
analysis = analyzer.analyze("Compare expenses between January and February")

print(f"Intent: {analysis.intent}")
print(f"Is comparison: {analysis.is_comparison}")
print(f"Entities: {analysis.entities}")
print(f"Temporal refs: {analysis.temporal_refs}")
```

### SemanticSearcher

```python
from src.query import SemanticSearcher

searcher = SemanticSearcher(embedding_service, vector_storage)

# Regular search
results = searcher.search(
    query="monthly revenue report",
    top_k=10
)

# Comparison search (returns diverse files)
comparison_results = searcher.search_for_comparison(
    query="compare Q1 and Q2 sales",
    max_files=5
)

for result in results.results:
    print(f"{result.file_name} - {result.sheet_name} (score: {result.score:.2f})")
```

### ConversationManager

```python
from src.query import ConversationManager

manager = ConversationManager(cache_service)

# Create session
session_id = manager.create_session()

# Update context
manager.update_context(
    session_id=session_id,
    query="What were the expenses?",
    selected_file="file123",
    selected_sheet="Summary"
)

# Get context
context = manager.get_context(session_id)
print(f"Previous queries: {context.previous_queries}")

# Resolve ambiguous references
resolved = manager.resolve_ambiguous_reference(
    query="What about last month?",
    session_id=session_id
)
```

### ClarificationGenerator

```python
from src.query import ClarificationGenerator

generator = ClarificationGenerator(llm_service)

# Check if clarification needed
needs_clarification = generator.needs_clarification(
    search_results=search_results,
    confidence=0.65
)

if needs_clarification:
    # Generate clarification
    clarification = generator.generate_file_clarification(
        query="expenses report",
        search_results=search_results,
        max_options=3
    )
    
    print(clarification.question)
    for i, option in enumerate(clarification.options, 1):
        print(f"{i}. {option.label} - {option.description}")
    
    # Handle user response
    user_choice = "1"  # User selects first option
    resolved = generator.handle_clarification_response(
        clarification_request=clarification,
        user_response=user_choice
    )
```

## Configuration

The query processing module uses the following configuration from `.env`:

```bash
# LLM Configuration (for query analysis and clarification)
LLM_PROVIDER=openai  # or anthropic, gemini
LLM_API_KEY=your_api_key
LLM_MODEL=gpt-4  # or claude-3-sonnet-20240229, gemini-pro

# Embedding Configuration (for semantic search)
EMBEDDING_PROVIDER=openai  # or sentence-transformers, cohere
EMBEDDING_API_KEY=your_api_key
EMBEDDING_MODEL=text-embedding-3-small

# Cache Configuration (for conversation context)
CACHE_PROVIDER=memory  # or redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Vector Store Configuration (for search)
VECTOR_STORE_PROVIDER=chromadb  # or opensearch
CHROMA_PERSIST_DIR=./chroma_db
```

## Dependencies

- `dateparser`: Temporal reference parsing
- `pydantic`: Data validation and models
- LLM service (OpenAI, Anthropic, or Gemini)
- Embedding service (OpenAI, Sentence Transformers, or Cohere)
- Cache service (Redis or in-memory)
- Vector store (ChromaDB or OpenSearch)

## Integration with Other Modules

The query processing module integrates with:

1. **Indexing Module** (`src/indexing/`): Uses VectorStorageManager for search
2. **Abstractions** (`src/abstractions/`): Uses LLM, embedding, and cache services
3. **Models** (`src/models/`): Uses domain models for data structures
4. **File Selection** (Task 9 - not yet implemented): Will use FileSelector
5. **Sheet Selection** (Task 9 - not yet implemented): Will use SheetSelector
6. **Comparison Engine** (Task 10 - not yet implemented): Will use ComparisonEngine
7. **Answer Generation** (Task 11 - not yet implemented): Will use AnswerGenerator

## Testing

See `tests/test_query_*.py` for unit tests (to be implemented in task 16).

## Performance Considerations

- **Query Analysis**: ~500-1000ms (LLM call)
- **Semantic Search**: ~100-300ms (embedding + vector search)
- **Clarification Generation**: ~500-1000ms (LLM call)
- **Context Management**: ~10-50ms (cache operations)
- **Total Pipeline**: ~1-3 seconds for typical queries

## Error Handling

All components include comprehensive error handling:
- LLM failures fall back to rule-based analysis
- Search errors return empty results
- Context errors create new sessions
- Clarification errors use fallback questions

## Future Enhancements

1. **Query Caching**: Cache common query patterns
2. **Query Suggestions**: Auto-complete based on indexed data
3. **Multi-turn Conversations**: Better context tracking
4. **Query Rewriting**: Improve ambiguous queries automatically
5. **Feedback Learning**: Learn from user corrections
6. **Batch Processing**: Process multiple queries in parallel
7. **Streaming Responses**: Stream answers as they're generated


## New Components (Task 9 - File and Sheet Selection)

### 6. FileSelector (`file_selector.py`)

Ranks and selects files based on multiple scoring factors:
- **Semantic Similarity**: 50% weight from vector search results
- **Metadata Matching**: 30% weight (dates, paths, recency)
- **User Preferences**: 20% weight from historical selections
- **Automatic Selection**: When confidence > 90%
- **Clarification Request**: When confidence < 90%
- **User Confirmation**: Handles user selection and "none of these" option

**Key Features:**
- Multi-factor ranking algorithm
- Date parsing from file names
- User preference learning with decay
- Automatic vs. manual selection
- Preference recording for future queries

### 7. SheetSelector (`sheet_selector.py`)

Selects relevant sheet(s) within an Excel file:
- **Sheet Name Similarity**: 30% weight using fuzzy matching
- **Header/Column Match**: 40% weight using keyword matching
- **Data Type Alignment**: 20% weight based on query intent
- **Content Sample Similarity**: 10% weight from embeddings
- **Parallel Processing**: ThreadPoolExecutor for multi-sheet scenarios
- **Combination Strategies**: Union, join, or separate for multi-sheet results

**Key Features:**
- Fuzzy matching with fuzzywuzzy
- Keyword extraction and matching
- Data type alignment scoring
- Parallel sheet processing (max 5 workers)
- Multi-sheet selection support
- Intelligent combination strategy determination

### 8. DateParser (`date_parser.py`)

Extracts and parses dates from file names and paths:
- **Multiple Formats**: ISO, US, compact, month-year, quarter, year
- **Regex Patterns**: Comprehensive date pattern matching
- **Confidence Scoring**: Each parsed date has confidence score
- **Temporal Matching**: Matches against query temporal references
- **Relative Dates**: Handles "last month", "this year", etc.

**Supported Formats:**
- `YYYY-MM-DD` (2024-01-15)
- `MM-DD-YYYY` (01-15-2024)
- `YYYYMMDD` (20240115)
- `Month YYYY` (January 2024, Jan2024)
- `Q1 2024`, `Q2 2024`, etc.
- Year only (2024)
- Month only (January, Jan)

### 9. PreferenceManager (`preference_manager.py`)

Manages user file selection preferences:
- **Historical Storage**: Stores query patterns and file selections
- **Fuzzy Matching**: Uses Levenshtein distance for similar queries
- **Exponential Decay**: Preferences decay after 30 days
- **Automatic Cleanup**: Removes preferences older than 90 days
- **Statistics**: Provides preference analytics

**Decay Model:**
- 0-30 days: No decay (factor = 1.0)
- 30-90 days: Exponential decay (half-life = 60 days)
- > 90 days: Minimum factor (0.1)

## Extended Usage Examples

### File Selection with Ranking

```python
from src.query import FileSelector, DateParser, PreferenceManager
from src.database.connection import DatabaseConnection
from src.indexing.metadata_storage import MetadataStorageManager

# Initialize components
db_connection = DatabaseConnection("data/metadata.db")
metadata_storage = MetadataStorageManager(db_connection)
date_parser = DateParser()
preference_manager = PreferenceManager(db_connection)

file_selector = FileSelector(
    metadata_storage=metadata_storage,
    date_parser=date_parser,
    preference_manager=preference_manager
)

# Rank files from search results
ranked_files = file_selector.rank_files(
    query="What were the expenses in January 2024?",
    search_results=search_results,
    temporal_refs=query_analysis.temporal_refs
)

# Display ranked files
for i, ranked_file in enumerate(ranked_files[:5], 1):
    print(f"{i}. {ranked_file.file_metadata.name}")
    print(f"   Relevance: {ranked_file.relevance_score:.3f}")
    print(f"   Semantic: {ranked_file.semantic_score:.3f}")
    print(f"   Metadata: {ranked_file.metadata_score:.3f}")
    print(f"   Preference: {ranked_file.preference_score:.3f}")

# Select file (automatic or with clarification)
file_selection = file_selector.select_file(ranked_files)

if file_selection.requires_clarification:
    # Present options to user
    print("Which file would you like to use?")
    for i, candidate in enumerate(file_selection.candidates, 1):
        print(f"{i}. {candidate.file_metadata.name} (score: {candidate.relevance_score:.3f})")
    print(f"{len(file_selection.candidates) + 1}. None of these")
    
    # Get user choice
    user_choice = int(input("Enter choice: ")) - 1
    
    # Handle selection
    selected_file = file_selector.handle_user_selection(
        query="What were the expenses in January 2024?",
        candidates=file_selection.candidates,
        user_choice=user_choice
    )
else:
    print(f"Auto-selected: {file_selection.selected_file.file_metadata.name}")
    selected_file = file_selection.selected_file
```

### Sheet Selection

```python
from src.query import SheetSelector
from src.text_processing.preprocessor import TextPreprocessor

# Initialize sheet selector
text_preprocessor = TextPreprocessor(config)
sheet_selector = SheetSelector(
    metadata_storage=metadata_storage,
    text_preprocessor=text_preprocessor
)

# Select single sheet
sheet_selection = sheet_selector.select_sheet(
    file_id=selected_file.file_metadata.file_id,
    query="What were the expenses in January 2024?",
    query_analysis=query_analysis,
    search_results=search_results
)

print(f"Selected sheet: {sheet_selection.sheet_name}")
print(f"Relevance: {sheet_selection.relevance_score:.3f}")

if sheet_selection.requires_clarification:
    print("Note: Low confidence, may need user confirmation")

# Select multiple sheets (for complex queries)
multi_sheet_selection = sheet_selector.select_multiple_sheets(
    file_id=selected_file.file_metadata.file_id,
    query="Compare expenses across all departments",
    query_analysis=query_analysis,
    search_results=search_results
)

print(f"Selected {len(multi_sheet_selection.selected_sheets)} sheets")
print(f"Combination strategy: {multi_sheet_selection.combination_strategy}")

for scored_sheet in multi_sheet_selection.selected_sheets:
    print(f"- {scored_sheet.sheet_data.sheet_name} (score: {scored_sheet.relevance_score:.3f})")
```

### Date Parsing

```python
from src.query import DateParser

date_parser = DateParser()

# Parse dates from filename
filename = "Expenses_Jan2024_Final.xlsx"
parsed_dates = date_parser.parse_dates_from_filename(filename)

for pd in parsed_dates:
    print(f"Found: {pd.text} -> {pd.date.strftime('%Y-%m-%d')}")
    print(f"  Format: {pd.format_type}, Confidence: {pd.confidence:.2f}")

# Match against temporal reference from query
temporal_ref = {
    "text": "January",
    "date": "2024-01-01T00:00:00",
    "type": "month"
}

if parsed_dates:
    match_score = date_parser.match_dates(parsed_dates[0], temporal_ref)
    print(f"Match score: {match_score:.2f}")
```

### Preference Management

```python
from src.query import PreferenceManager

preference_manager = PreferenceManager(db_connection)

# Record a preference after user selection
preference_manager.record_preference(
    query="What were the expenses in January?",
    file_id="file123",
    sheet_name="Summary"
)

# Get preferences for similar query
preferences = preference_manager.get_preferences(
    query="January expenses",
    max_results=5
)

print("Historical preferences for similar queries:")
for pref in preferences:
    print(f"- File: {pref['file_id']}")
    print(f"  Query: {pref['query_pattern']}")
    print(f"  Score: {pref['score']:.3f} (similarity: {pref['similarity']:.2f}, decay: {pref['decay']:.2f})")
    print(f"  Created: {pref['created_at']}")

# Get statistics
stats = preference_manager.get_preference_statistics()
print(f"\nTotal preferences: {stats['total_preferences']}")
print(f"Recent (7 days): {stats['recent_preferences']}")
print(f"Top files: {stats['top_files'][:3]}")

# Clean up old preferences
deleted = preference_manager.clear_old_preferences(days=90)
print(f"Deleted {deleted} preferences older than 90 days")
```

## Additional Dependencies (Task 9)

- `fuzzywuzzy`: Fuzzy string matching for sheet names
- `python-Levenshtein`: Fast Levenshtein distance calculation
- `dateparser`: Already included for temporal parsing

## Complete Pipeline Example

```python
from src.config import AppConfig
from src.query import (
    QueryAnalyzer, SemanticSearcher, FileSelector, SheetSelector,
    DateParser, PreferenceManager
)

# Initialize all components
config = AppConfig.from_env()
# ... (initialize services as shown above)

# Complete query processing pipeline
query = "What were the total expenses in January 2024?"

# 1. Analyze query
analysis = query_analyzer.analyze(query)

# 2. Semantic search
search_results = semantic_searcher.search(
    query=query,
    query_analysis=analysis,
    top_k=10
)

# 3. Rank and select file
ranked_files = file_selector.rank_files(
    query=query,
    search_results=search_results,
    temporal_refs=analysis.temporal_refs
)

file_selection = file_selector.select_file(ranked_files)

if file_selection.requires_clarification:
    # Handle user selection...
    selected_file = file_selector.handle_user_selection(
        query=query,
        candidates=file_selection.candidates,
        user_choice=0  # User's choice
    )
else:
    selected_file = file_selection.selected_file

# 4. Select sheet
sheet_selection = sheet_selector.select_sheet(
    file_id=selected_file.file_metadata.file_id,
    query=query,
    query_analysis=analysis,
    search_results=search_results
)

# 5. Retrieve data and generate answer (tasks 10-11)
# ... (to be implemented)

print(f"Selected: {selected_file.file_metadata.name} / {sheet_selection.sheet_name}")
```

## Performance Metrics (Task 9 Components)

- **File Ranking**: ~50-100ms for 10-20 files
- **Date Parsing**: ~10-20ms per filename
- **Preference Lookup**: ~20-50ms (database query with fuzzy matching)
- **Sheet Selection**: ~100-200ms for 5-10 sheets
- **Multi-Sheet Selection**: ~200-500ms (parallel processing)

## Testing (Task 9)

Unit tests for file and sheet selection components will be added in task 16:
- `tests/test_file_selector.py`
- `tests/test_sheet_selector.py`
- `tests/test_date_parser.py`
- `tests/test_preference_manager.py`
