# Google Drive Excel RAG System - Solution Architecture

## Executive Summary

The Google Drive Excel RAG (Retrieval-Augmented Generation) System is a comprehensive, production-ready application that enables users to query Excel files stored in Google Drive using natural language. The system combines OAuth 2.0 authentication, intelligent file indexing, semantic search, and LLM-powered answer generation into a unified platform.

**Key Characteristics:**
- **Modular Architecture**: Pluggable abstractions for vector stores, embeddings, and LLMs
- **Smart Query Pipeline**: Intelligent file/sheet selection, query classification, and answer generation with citations
- **Chunk Visibility**: Full debugging and traceability for indexed data
- **Enterprise Features**: Access control, audit logging, batch processing, webhooks, and data lineage
- **Multi-Language Support**: English and Thai with language detection and specialized tokenization
- **Scalable Design**: From MVP (ChromaDB + Ollama) to production (OpenSearch + Claude)
- **Full-Stack**: Python backend (FastAPI), React frontend, Docker deployment
- **Open-Source Option**: Run fully locally with Ollama, BGE-M3, and ChromaDB (zero API costs)

---

## System Architecture Overview

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           User Interface                                     │
│                       (React + Material-UI)                                  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                         FastAPI Backend                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ API Layer (REST Endpoints)                                             │ │
│  │ - Authentication (/auth)          - Chunk Visibility (/chunks)         │ │
│  │ - File Management (/files)        - Smart Query Pipeline (/query)      │ │
│  │ - Indexing (/index)               - Batch Processing (/query/batch)    │ │
│  │ - Chat Sessions (/chat)           - Templates (/query/templates)       │ │
│  │ - Export (/export)                - Webhooks (/webhooks)               │ │
│  │ - Intelligence (/intelligence)    - Traceability (/trace, /lineage)    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                 │                                        │ │
│  ┌──────────────────────────────▼────────────────────────────────────────┐ │
│  │ Core Processing Layers                                                │ │
│  │ ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │ │ Smart Query Pipeline (NEW)                                       │ │ │
│  │ │ - QueryPipelineOrchestrator: Coordinates full query flow         │ │ │
│  │ │ - FileSelector: Ranks files by relevance (semantic + metadata)   │ │ │
│  │ │ - SheetSelector: Identifies relevant sheets within files         │ │ │
│  │ │ - QueryClassifier: Classifies query type (aggregation/lookup/etc)│ │ │
│  │ │ - Query Processors: Aggregation, Lookup, Summarization, Compare  │ │ │
│  │ │ - AnswerGenerator: Generates answers with citations              │ │ │
│  │ │ - TraceRecorder: Records complete audit trail                    │ │ │
│  │ │ - DataLineageTracker: Tracks data from source to answer          │ │ │
│  │ └──────────────────────────────────────────────────────────────────┘ │ │
│  │ ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │ │ Chunk Visibility (NEW)                                           │ │ │
│  │ │ - ChunkViewer: View/search/filter indexed chunks                 │ │ │
│  │ │ - ChunkVersionStore: Track chunk changes across re-indexing      │ │ │
│  │ │ - FeedbackCollector: Collect user feedback on chunk quality      │ │ │
│  │ │ - ExtractionQualityScorer: Score extraction quality              │ │ │
│  │ └──────────────────────────────────────────────────────────────────┘ │ │
│  │ ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │ │ Intelligence Features (NEW)                                      │ │ │
│  │ │ - DateParser: Parse natural language dates (Q1, YTD, last month) │ │ │
│  │ │ - UnitAwarenessService: Handle units ($, %, kg) in aggregations  │ │ │
│  │ │ - AnomalyDetector: Detect outliers and data quality issues       │ │ │
│  │ │ - RelationshipDetector: Find relationships between files         │ │ │
│  │ └──────────────────────────────────────────────────────────────────┘ │ │
│  │ ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │ │ Enterprise Features (NEW)                                        │ │ │
│  │ │ - AccessController: Role-based access control (RBAC)             │ │ │
│  │ │ - BatchQueryProcessor: Process up to 100 queries in parallel     │ │ │
│  │ │ - TemplateManager: Parameterized query templates                 │ │ │
│  │ │ - WebhookManager: Event notifications with retry                 │ │ │
│  │ │ - ExportService: Export to CSV, Excel, JSON                      │ │ │
│  │ │ - QueryCache: Cache query results with TTL                       │ │ │
│  │ └──────────────────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ Enhanced Extraction Layer (NEW)                                      │ │
│  │ - EnhancedOpenpyxlExtractor: Formula, pivot, chart, merged cells     │ │
│  │ - StreamingExtractor: Handle files >100MB with chunked processing    │ │
│  │ - IncrementalIndexer: Detect changes and update only modified chunks │ │
│  │ - LanguageDetection: Detect content language for multilingual support│ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
┌───────▼────────┐    ┌─────────▼─────────┐    ┌────────▼────────┐
│  Vector Store  │    │   Metadata DB     │    │  Cache Service  │
│ (ChromaDB or   │    │    (SQLite)       │    │ (Memory/Redis)  │
│  OpenSearch)   │    │                   │    │                 │
└────────────────┘    └───────────────────┘    └─────────────────┘
```

---

## Core Components

### 1. Smart Query Pipeline (NEW)

The Smart Query Pipeline is the central intelligence layer that processes natural language queries through a sophisticated multi-stage pipeline.

#### Query Pipeline Orchestrator

```python
class QueryPipelineOrchestrator:
    """
    Orchestrates the smart query pipeline.
    
    Coordinates file selection, sheet selection, query classification,
    processing, and answer generation with full traceability.
    """
    
    def __init__(
        self,
        file_selector: FileSelector,
        sheet_selector: SheetSelector,
        query_classifier: QueryClassifier,
        processor_registry: QueryProcessorRegistry,
        answer_generator: AnswerGenerator,
        trace_recorder: TraceRecorder,
        cache_service: CacheService,
        config: QueryPipelineConfig
    ) -> None:
        # All dependencies injected - follows DIP
        ...
    
    def process_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        file_hints: Optional[list[str]] = None,
        sheet_hints: Optional[list[str]] = None
    ) -> QueryResponse:
        """Process query through full pipeline with traceability."""
        ...
```

#### Query Classification

The system classifies queries into four types:

| Query Type | Keywords | Example |
|------------|----------|---------|
| Aggregation | sum, total, average, count, min, max | "What is the total revenue?" |
| Lookup | what is, find, show me, value of | "Show me the Q1 expenses" |
| Summarization | summarize, describe, overview | "Summarize the sales data" |
| Comparison | compare, difference, versus, trend | "Compare Q1 vs Q2 sales" |

#### Query Processors (Registry Pattern)

```python
class QueryProcessorRegistry:
    """
    Registry for query processors following Open/Closed Principle.
    New processors can be registered without modifying existing code.
    """
    
    _processors: dict[QueryType, type[BaseQueryProcessor]] = {}
    
    @classmethod
    def register(cls, query_type: QueryType):
        """Decorator to register a processor for a query type."""
        def decorator(processor_class):
            cls._processors[query_type] = processor_class
            return processor_class
        return decorator

@QueryProcessorRegistry.register(QueryType.AGGREGATION)
class AggregationProcessor(BaseQueryProcessor):
    """Processes SUM, AVERAGE, COUNT, MIN, MAX, MEDIAN queries."""
    ...

@QueryProcessorRegistry.register(QueryType.LOOKUP)
class LookupProcessor(BaseQueryProcessor):
    """Processes specific value lookups with formatting preservation."""
    ...

@QueryProcessorRegistry.register(QueryType.SUMMARIZATION)
class SummarizationProcessor(BaseQueryProcessor):
    """Generates natural language summaries with statistics."""
    ...

@QueryProcessorRegistry.register(QueryType.COMPARISON)
class ComparisonProcessor(BaseQueryProcessor):
    """Compares data across files, sheets, or time periods."""
    ...
```

#### File and Sheet Selection

**File Selection** uses weighted scoring:
- Semantic similarity: 50%
- Metadata matching: 30%
- User preference history: 20%

**Confidence Thresholds:**
- >0.9: Auto-select without confirmation
- 0.5-0.9: Present top 3 candidates for user selection
- <0.5: Request clarification

**Sheet Selection** uses weighted scoring:
- Sheet name similarity: 30%
- Header/column matching: 40%
- Data type alignment: 20%
- Content similarity: 10%

### 2. Chunk Visibility System (NEW)

Provides complete visibility into indexed data for debugging and quality assurance.

```python
class ChunkViewer:
    """
    Provides chunk visibility and debugging capabilities.
    Supports viewing, searching, filtering, and comparing chunks.
    """
    
    def get_chunks_for_file(
        self,
        file_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedChunkResponse:
        """Get all chunks for a file with pagination."""
        ...
    
    def search_chunks(
        self,
        query: str,
        filters: Optional[ChunkFilters] = None
    ) -> PaginatedChunkResponse:
        """Search chunks with semantic similarity and filters."""
        ...
    
    def compare_extraction_strategies(
        self,
        file_id: str,
        strategies: list[str]
    ) -> StrategyComparisonResult:
        """Compare same file processed with different strategies."""
        ...
```

#### Chunk Details Include:
- Chunk text and raw source data
- Row range and chunk boundaries
- Extraction strategy used
- Embedding metadata (dimensions, token count, model)
- Quality scores
- Version history

### 3. Traceability Layer (NEW)

Enterprise-grade audit trail for compliance and debugging.

#### Query Trace

```python
@dataclass
class QueryTrace:
    """Complete audit record of query processing."""
    trace_id: str
    query_text: str
    timestamp: str
    user_id: Optional[str]
    session_id: Optional[str]
    
    # File selection
    file_candidates: list[FileCandidate]
    file_selection_reasoning: str
    selected_file_id: str
    file_confidence: float
    
    # Sheet selection
    sheet_candidates: list[SheetCandidate]
    selected_sheets: list[str]
    sheet_confidence: float
    
    # Query classification
    query_type: QueryType
    classification_confidence: float
    
    # Answer generation
    answer_text: str
    citations: list[Citation]
    answer_confidence: float
    
    # Performance
    total_processing_time_ms: int
```

#### Data Lineage

```python
@dataclass
class DataLineage:
    """Complete data path from source to answer."""
    lineage_id: str
    answer_component: str
    
    # Source information
    file_id: str
    file_name: str
    sheet_name: str
    cell_range: str
    source_value: str
    
    # Processing path
    chunk_id: str
    embedding_id: str
    retrieval_score: float
    
    # Timestamps
    indexed_at: str
    last_verified_at: Optional[str]
    is_stale: bool
```

### 4. Enhanced Extraction Layer (NEW)

Extended extraction with Excel-specific feature detection.

#### Supported Excel Features

| Feature | Detection | Extraction |
|---------|-----------|------------|
| Formulas | ✅ | Both formula text and computed value |
| Pivot Tables | ✅ | Structure, fields, aggregation types |
| Charts | ✅ | Type, title, axis labels, data series |
| Merged Cells | ✅ | Range and expanded values |
| Named Ranges | ✅ | Name, range, scope |
| Excel Tables | ✅ | Name, headers, row count |
| Hidden Content | ✅ | Hidden sheets, rows, columns |
| Conditional Formatting | ✅ | Rules and affected ranges |
| Data Validation | ✅ | Validation rules and allowed values |

#### Quality Scoring

```python
class ExtractionQualityScorer:
    """
    Computes quality score (0-1) based on:
    - data_completeness
    - structure_clarity
    - has_headers
    - has_data
    - error_count
    
    Files with quality < 0.5 are flagged as problematic.
    """
```

### 5. Intelligence Features (NEW)

#### Date Parser
Parses natural language date references:
- "last quarter", "YTD", "Q1 2024"
- "past 6 months", "January 2024"
- Supports fiscal year configurations
- Handles multiple date formats (MM/DD/YYYY, DD/MM/YYYY, YYYY-MM-DD)

#### Unit Awareness
- Detects and preserves units ($, €, %, kg, miles)
- Performs unit-aware aggregations
- Warns on unit mismatch in comparisons
- Includes units in numeric answers

#### Anomaly Detection
- Detects numeric outliers using IQR and Z-score
- Identifies missing values and duplicates
- Flags inconsistent formatting

#### Relationship Detection
- Detects relationships between files based on common columns
- Supports implicit joins across files
- Suggests related files during selection

### 6. Enterprise Features (NEW)

#### Access Control

```python
class AccessController:
    """
    Role-based access control with file-level restrictions.
    
    Roles: admin, developer, analyst, viewer
    """
    
    def check_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str
    ) -> bool:
        """Check if user has permission for action."""
        ...
    
    def log_access_attempt(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        granted: bool
    ) -> None:
        """Log access attempt for audit."""
        ...
```

#### Batch Processing
- Process up to 100 queries in parallel
- Individual status tracking per query
- Continue on partial failures
- Progress tracking via batch_id

#### Query Templates
- Parameterized templates with `{{parameter_name}}` syntax
- Template sharing within organization
- Execute templates with parameter substitution

#### Webhooks
- Events: indexing_complete, query_failed, low_confidence_answer, batch_complete
- Retry with exponential backoff (3 attempts)
- Delivery history tracking

#### Export
- Formats: CSV, Excel (.xlsx), JSON
- Preserves data types and formatting
- Scheduled exports for recurring reports

#### Query Caching
- Configurable TTL (default 1 hour)
- Intelligent cache key generation for semantically equivalent queries
- Cache invalidation on re-indexing

---

## API Endpoints

### Chunk Visibility API (NEW)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/chunks/{file_id}` | Get all chunks for a file |
| GET | `/api/v1/chunks/{file_id}/sheets/{sheet_name}` | Get chunks for a sheet |
| POST | `/api/v1/chunks/search` | Search chunks with filters |
| GET | `/api/v1/files/{file_id}/extraction-metadata` | Get extraction details |
| GET | `/api/v1/chunks/{file_id}/versions` | Get chunk version history |
| POST | `/api/v1/chunks/{chunk_id}/feedback` | Submit chunk feedback |
| GET | `/api/v1/chunks/feedback-summary` | Get aggregated feedback |
| GET | `/api/v1/files/quality-report` | Get quality scores for all files |

### Smart Query Pipeline API (NEW)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/query/smart` | Process natural language query |
| POST | `/api/v1/query/clarify` | Respond to clarification request |
| GET | `/api/v1/query/classify` | Get query type classification |
| GET | `/api/v1/query/trace/{trace_id}` | Get complete query trace |
| GET | `/api/v1/lineage/{lineage_id}` | Get data lineage |

### Batch and Template API (NEW)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/query/batch` | Submit batch queries (max 100) |
| GET | `/api/v1/query/batch/{batch_id}/status` | Get batch status |
| POST | `/api/v1/query/templates` | Create query template |
| POST | `/api/v1/query/templates/{template_id}/execute` | Execute template |
| GET | `/api/v1/query/templates` | List all templates |

### Export and Webhook API (NEW)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/export` | Export results (CSV/Excel/JSON) |
| POST | `/api/v1/webhooks` | Register webhook |
| GET | `/api/v1/webhooks/{webhook_id}/deliveries` | Get delivery history |

### Intelligence API (NEW)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/query/suggestions` | Get query suggestions |
| GET | `/api/v1/files/{file_id}/anomalies` | Get detected anomalies |
| GET | `/api/v1/usage/summary` | Get query cost statistics |

---

## Database Schema (Extended)

### New Tables

```sql
-- Chunk versions for tracking re-indexing changes
CREATE TABLE chunk_versions (
    id INTEGER PRIMARY KEY,
    chunk_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    extraction_strategy TEXT NOT NULL,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    change_summary TEXT
);

-- Query traces for audit
CREATE TABLE query_traces (
    trace_id TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    user_id TEXT,
    session_id TEXT,
    file_selection_json TEXT,
    sheet_selection_json TEXT,
    query_type TEXT,
    answer_text TEXT,
    citations_json TEXT,
    answer_confidence REAL,
    total_processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data lineage records
CREATE TABLE data_lineage (
    lineage_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    answer_component TEXT NOT NULL,
    file_id TEXT NOT NULL,
    sheet_name TEXT NOT NULL,
    cell_range TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    is_stale BOOLEAN DEFAULT 0
);

-- Extraction metadata
CREATE TABLE extraction_metadata (
    file_id TEXT PRIMARY KEY,
    strategy_used TEXT NOT NULL,
    quality_score REAL NOT NULL,
    has_headers BOOLEAN,
    extraction_duration_ms INTEGER,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Access control
CREATE TABLE file_access_control (
    file_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (file_id, user_id)
);

-- Query templates
CREATE TABLE query_templates (
    template_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    template_text TEXT NOT NULL,
    parameters TEXT NOT NULL,
    created_by TEXT NOT NULL,
    is_shared BOOLEAN DEFAULT 0
);

-- Webhooks
CREATE TABLE webhooks (
    webhook_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    events TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1
);
```

---

## Project Structure (Updated)

```
excel-rag/
├── src/
│   ├── abstractions/           # Pluggable service abstractions
│   │   ├── vector_store.py     # Vector store interface
│   │   ├── chromadb_store.py   # ChromaDB implementation
│   │   ├── opensearch_store.py # OpenSearch implementation
│   │   ├── embedding_service.py
│   │   ├── bge_embedding_service.py  # BGE-M3 (local, multilingual)
│   │   ├── llm_service.py
│   │   ├── ollama_llm_service.py     # Ollama (local)
│   │   ├── cache_service.py
│   │   └── redis_cache.py
│   ├── access_control/         # NEW: Role-based access control
│   │   ├── controller.py       # AccessController
│   │   ├── store.py            # Access control storage
│   │   └── audit_logger.py     # Audit logging
│   ├── api/
│   │   ├── routes/             # NEW: Modular API routes
│   │   │   ├── chunks.py       # Chunk visibility endpoints
│   │   │   ├── query.py        # Smart query pipeline endpoints
│   │   │   ├── batch.py        # Batch and template endpoints
│   │   │   ├── export.py       # Export and webhook endpoints
│   │   │   └── intelligence.py # Intelligence endpoints
│   │   ├── auth.py
│   │   ├── files.py
│   │   └── ...
│   ├── batch/                  # NEW: Batch processing
│   │   ├── processor.py        # BatchQueryProcessor
│   │   └── store.py            # Batch job storage
│   ├── cache/                  # NEW: Query caching
│   │   ├── query_cache.py      # QueryCache with TTL
│   │   └── invalidation_service.py
│   ├── chunk_viewer/           # NEW: Chunk visibility
│   │   ├── viewer.py           # ChunkViewer service
│   │   ├── metadata_store.py   # ChunkMetadataStore
│   │   ├── version_store.py    # ChunkVersionStore
│   │   └── feedback.py         # FeedbackCollector
│   ├── export/                 # NEW: Export capabilities
│   │   ├── service.py          # ExportService
│   │   └── store.py            # Export job storage
│   ├── extraction/
│   │   ├── enhanced_strategy.py    # NEW: Enhanced extraction base
│   │   ├── enhanced_openpyxl.py    # NEW: Formula/pivot/chart extraction
│   │   ├── streaming.py            # NEW: Large file streaming
│   │   ├── incremental.py          # NEW: Incremental indexing
│   │   ├── quality_scorer.py       # NEW: Quality scoring
│   │   ├── language_detection.py   # NEW: Language detection
│   │   └── ...
│   ├── intelligence/           # NEW: Intelligence features
│   │   ├── date_parser.py      # Natural language date parsing
│   │   ├── unit_awareness.py   # Unit detection and handling
│   │   ├── anomaly_detector.py # Outlier and quality detection
│   │   └── relationship_detector.py  # Cross-file relationships
│   ├── models/                 # NEW: Domain models
│   │   ├── query_pipeline.py   # Query pipeline models
│   │   ├── chunk_visibility.py # Chunk visibility models
│   │   ├── traceability.py     # Trace and lineage models
│   │   ├── excel_features.py   # Excel-specific models
│   │   └── enterprise.py       # Enterprise feature models
│   ├── query_pipeline/         # NEW: Smart query pipeline
│   │   ├── orchestrator.py     # QueryPipelineOrchestrator
│   │   ├── file_selector.py    # FileSelector
│   │   ├── sheet_selector.py   # SheetSelector
│   │   ├── classifier.py       # QueryClassifier
│   │   ├── answer_generator.py # AnswerGenerator
│   │   ├── processor_registry.py
│   │   ├── processors/
│   │   │   ├── base.py         # BaseQueryProcessor
│   │   │   ├── aggregation.py  # AggregationProcessor
│   │   │   ├── lookup.py       # LookupProcessor
│   │   │   ├── summarization.py
│   │   │   └── comparison.py   # ComparisonProcessor
│   │   ├── config.py
│   │   └── cost_estimator.py   # Query cost estimation
│   ├── templates/              # NEW: Query templates
│   │   ├── manager.py          # TemplateManager
│   │   └── store.py            # Template storage
│   ├── traceability/           # NEW: Audit and lineage
│   │   ├── trace_recorder.py   # TraceRecorder
│   │   ├── trace_storage.py    # Trace storage
│   │   ├── lineage_tracker.py  # DataLineageTracker
│   │   └── lineage_storage.py  # Lineage storage
│   ├── webhooks/               # NEW: Webhook system
│   │   ├── manager.py          # WebhookManager
│   │   └── store.py            # Webhook storage
│   ├── container.py            # NEW: Dependency injection container
│   ├── exceptions.py           # Extended exception hierarchy
│   └── ...
├── frontend/
├── tests/
└── docs/
```

---

## Configuration Options (Extended)

### Smart Query Pipeline Configuration

```bash
# Query Pipeline
QUERY_PIPELINE_TIMEOUT=30              # Timeout in seconds
FILE_SELECTION_THRESHOLD_HIGH=0.9      # Auto-select threshold
FILE_SELECTION_THRESHOLD_LOW=0.5       # Clarification threshold
SHEET_SELECTION_THRESHOLD=0.7          # Sheet auto-select threshold

# Query Classification
CLASSIFICATION_CONFIDENCE_THRESHOLD=0.6  # Below this, show alternatives

# Caching
QUERY_CACHE_TTL=3600                   # Cache TTL in seconds (1 hour)
QUERY_CACHE_ENABLED=true               # Enable/disable caching

# Batch Processing
BATCH_MAX_QUERIES=100                  # Maximum queries per batch
BATCH_PARALLEL_WORKERS=5               # Parallel processing workers

# Traceability
TRACE_RETENTION_DAYS=90                # Trace retention period
ENABLE_DATA_LINEAGE=true               # Enable lineage tracking
```

### Access Control Configuration

```bash
# Access Control
ACCESS_CONTROL_ENABLED=true            # Enable RBAC
DEFAULT_USER_ROLE=viewer               # Default role for new users
AUDIT_LOG_ENABLED=true                 # Enable audit logging
```

### Extraction Configuration

```bash
# Enhanced Extraction
EXTRACT_FORMULAS=true                  # Extract formula text and values
EXTRACT_PIVOT_TABLES=true              # Extract pivot table data
EXTRACT_CHARTS=true                    # Extract chart metadata
DETECT_HIDDEN_CONTENT=true             # Detect hidden sheets/rows/cols
QUALITY_THRESHOLD=0.5                  # Flag files below this score

# Streaming (Large Files)
STREAMING_THRESHOLD_MB=100             # Use streaming above this size
STREAMING_CHUNK_SIZE=10000             # Rows per chunk
MAX_MEMORY_MB=1024                     # Memory limit for extraction
```

### Intelligence Configuration

```bash
# Date Parsing
FISCAL_YEAR_START_MONTH=1              # Fiscal year start (1=January)
DEFAULT_DATE_FORMAT=MM/DD/YYYY         # Default date format

# Anomaly Detection
OUTLIER_IQR_MULTIPLIER=1.5             # IQR multiplier for outliers
OUTLIER_ZSCORE_THRESHOLD=3.0           # Z-score threshold
```

---

## Performance Characteristics (Updated)

### Query Pipeline Performance

| Operation | Target | Notes |
|-----------|--------|-------|
| File Selection | <500ms | For up to 1000 indexed files |
| Sheet Selection | <200ms | For files with up to 50 sheets |
| Query Classification | <100ms | Pattern matching + LLM fallback |
| Aggregation Query | <2s | For datasets up to 100,000 rows |
| Lookup Query | <1s | For datasets up to 100,000 rows |
| Chunk Listing | <500ms | For files with up to 1000 chunks |

### Caching Performance

| Scenario | Improvement |
|----------|-------------|
| Cache Hit | 10-100x faster (skip LLM calls) |
| Semantic Equivalence | Matches similar queries |
| Invalidation | Automatic on re-indexing |

---

## Security Considerations (Extended)

### Access Control
- Role-based access control (RBAC) with four roles: admin, developer, analyst, viewer
- File-level access restrictions
- All access attempts logged for audit
- 403 Forbidden for unauthorized access

### Data Protection
- Encrypted token storage (Fernet)
- Data masking for sensitive columns
- Query traces stored with configurable retention
- Data lineage for compliance audits

### API Security
- JWT token validation
- Rate limiting on all endpoints
- Correlation IDs for request tracing
- Input validation via Pydantic models

---

## Monitoring and Observability (Extended)

### New Metrics

| Metric | Description |
|--------|-------------|
| query_pipeline_duration_ms | Total pipeline processing time |
| file_selection_confidence | File selection confidence scores |
| query_classification_accuracy | Classification confidence distribution |
| cache_hit_rate | Query cache hit percentage |
| batch_query_throughput | Queries processed per second |
| extraction_quality_scores | Distribution of quality scores |
| access_denied_count | Access control denials |

### Health Checks

```json
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "vector_store": "healthy",
    "cache": "healthy",
    "query_pipeline": "healthy",
    "chunk_viewer": "healthy",
    "access_control": "healthy"
  }
}
```

---

## Key Design Decisions (Extended)

### 1. Registry Pattern for Query Processors
**Decision**: Use decorator-based registry for query processors
**Rationale**: Follow Open/Closed Principle - add new processors without modifying existing code
**Benefit**: Easy to extend with custom query types

### 2. Dependency Injection Container
**Decision**: Centralized DI container in `src/container.py`
**Rationale**: Follow Dependency Inversion Principle - depend on abstractions
**Benefit**: Testable, configurable, no module-level state

### 3. Complete Traceability
**Decision**: Record full audit trail for every query
**Rationale**: Enterprise compliance requirements
**Benefit**: Debug issues, audit decisions, meet regulatory requirements

### 4. Data Lineage Tracking
**Decision**: Track data path from source cell to answer
**Rationale**: Compliance officers need to verify data accuracy
**Benefit**: Full transparency, staleness detection

### 5. Chunk Versioning
**Decision**: Preserve chunk history across re-indexing
**Rationale**: Understand what changed and debug retrieval differences
**Benefit**: Diff comparison, rollback capability

### 6. Intelligent Caching
**Decision**: Cache query results with semantic equivalence matching
**Rationale**: Reduce LLM costs and improve response times
**Benefit**: 10-100x faster for repeated/similar queries

---

## Data Flow Examples (Extended)

### Smart Query Flow

```
1. User submits: "What was the total revenue in Q1 2024?"
   │
2. QueryPipelineOrchestrator.process_query()
   │
3. TraceRecorder.start_trace() → trace_id generated
   │
4. FileSelector.rank_files()
   ├── Semantic similarity: 50%
   ├── Metadata matching: 30%
   ├── User preferences: 20%
   └── Result: sales_2024.xlsx (confidence: 0.95)
   │
5. SheetSelector.select_sheets()
   ├── Name matching: 30%
   ├── Header matching: 40%
   └── Result: "Q1" sheet (confidence: 0.92)
   │
6. QueryClassifier.classify()
   └── Result: AGGREGATION (confidence: 0.98)
   │
7. AggregationProcessor.process()
   ├── Identify column: "Revenue"
   ├── Apply filter: Q1 2024
   └── Compute: SUM = $1,234,567
   │
8. AnswerGenerator.generate()
   ├── Generate answer with citations
   ├── Create data lineage records
   └── Calculate confidence breakdown
   │
9. TraceRecorder.complete_trace()
   │
10. Return QueryResponse with:
    ├── answer: "The total revenue in Q1 2024 was $1,234,567"
    ├── citations: [File: sales_2024.xlsx, Sheet: Q1, Range: B2:B100]
    ├── confidence: 0.95
    ├── trace_id: "tr_abc123"
    └── processing_time_ms: 1250
```

### Chunk Visibility Flow

```
1. Developer requests: GET /api/v1/chunks/{file_id}
   │
2. AccessController.check_access() → Verify permissions
   │
3. ChunkViewer.get_chunks_for_file()
   ├── Query ChunkMetadataStore
   ├── Include extraction metadata
   ├── Include quality scores
   └── Apply pagination
   │
4. Return PaginatedChunkResponse with:
    ├── chunks: [ChunkDetails...]
    ├── total_count: 150
    ├── page: 1
    └── has_more: true
```

---

## Conclusion

The Google Drive Excel RAG System has evolved into a comprehensive, enterprise-ready platform with:

- **Smart Query Pipeline**: Intelligent file/sheet selection, query classification, and answer generation
- **Full Traceability**: Complete audit trail from query to answer with data lineage
- **Chunk Visibility**: Debug and inspect indexed data with version tracking
- **Enterprise Features**: Access control, batch processing, templates, webhooks, export
- **Intelligence Layer**: Date parsing, unit awareness, anomaly detection, relationship detection
- **Open-Source Option**: Run fully locally with Ollama, BGE-M3, and ChromaDB

The modular architecture, SOLID design principles, and pluggable abstractions make it suitable for both MVP deployments and enterprise-scale production environments.
