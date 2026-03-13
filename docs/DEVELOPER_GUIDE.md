# Google Drive Excel RAG System - Developer Guide

Technical documentation for developers working on or integrating with the system.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Development Setup](#development-setup)
3. [Project Structure](#project-structure)
4. [Core Components](#core-components)
5. [Smart Query Pipeline](#smart-query-pipeline)
6. [Chunk Visibility](#chunk-visibility)
7. [Enterprise Features](#enterprise-features)
8. [Adding New Features](#adding-new-features)
9. [Testing](#testing)
10. [Configuration](#configuration)

---

## Architecture Overview

The system follows a modular, layered architecture with pluggable abstractions:

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│              (React Frontend + FastAPI REST)                 │
├─────────────────────────────────────────────────────────────┤
│                    Application Layer                         │
│  (Query Pipeline, Chunk Viewer, Batch Processor, etc.)       │
├─────────────────────────────────────────────────────────────┤
│                    Domain Layer                              │
│        (Domain Models, Business Logic, Validators)           │
├─────────────────────────────────────────────────────────────┤
│                    Infrastructure Layer                      │
│   (Vector Store, Database, Cache, External APIs)             │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **SOLID Principles** - All components follow SOLID design principles
2. **Dependency Injection** - Services are injected via constructor (DIP)
3. **Registry Pattern** - Pluggable implementations for processors (OCP)
4. **No Module-Level State** - All state managed via injected services
5. **Type Safety** - All functions have type hints

---

## Development Setup

### Prerequisites

- Python 3.9+
- Node.js 20.19+ or 22.12+
- Docker (optional)

### Backend Setup

```bash
# Clone repository
git clone <repository-url>
cd gdrive-excel-rag

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Run database migrations
python -c "from src.database.migrations import run_migrations; run_migrations()"

# Start development server
uvicorn src.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

---

## Project Structure

```
src/
├── abstractions/           # Pluggable service abstractions
│   ├── vector_store.py     # Vector store interface
│   ├── embedding_service.py
│   ├── llm_service.py
│   └── cache_service.py
├── access_control/         # Role-based access control
│   ├── controller.py       # AccessController
│   └── audit_logger.py
├── api/
│   ├── routes/             # Modular API routes
│   │   ├── chunks.py       # Chunk visibility endpoints
│   │   ├── query.py        # Smart query pipeline
│   │   ├── batch.py        # Batch processing
│   │   ├── export.py       # Export endpoints
│   │   └── intelligence.py
│   └── dependencies.py     # Dependency injection
├── batch/                  # Batch query processing
│   └── processor.py        # BatchQueryProcessor
├── cache/                  # Query caching
│   ├── query_cache.py      # QueryCache
│   └── invalidation_service.py
├── chunk_viewer/           # Chunk visibility
│   ├── viewer.py           # ChunkViewer
│   ├── version_store.py    # ChunkVersionStore
│   └── feedback.py         # FeedbackCollector
├── extraction/             # Excel extraction
│   ├── enhanced_openpyxl.py    # Formula/pivot/chart extraction
│   ├── streaming.py            # Large file streaming
│   └── quality_scorer.py       # Quality scoring
├── intelligence/           # Intelligence features
│   ├── date_parser.py      # Natural language dates
│   ├── unit_awareness.py   # Unit handling
│   └── anomaly_detector.py
├── models/                 # Domain models
│   ├── query_pipeline.py
│   ├── chunk_visibility.py
│   └── traceability.py
├── query_pipeline/         # Smart query pipeline
│   ├── orchestrator.py     # QueryPipelineOrchestrator
│   ├── file_selector.py    # FileSelector
│   ├── sheet_selector.py   # SheetSelector
│   ├── classifier.py       # QueryClassifier
│   ├── answer_generator.py
│   └── processors/         # Query processors
│       ├── aggregation.py
│       ├── lookup.py
│       ├── summarization.py
│       └── comparison.py
├── templates/              # Query templates
│   └── manager.py          # TemplateManager
├── traceability/           # Audit and lineage
│   ├── trace_recorder.py   # TraceRecorder
│   └── lineage_tracker.py  # DataLineageTracker
├── webhooks/               # Webhook system
│   └── manager.py          # WebhookManager
├── container.py            # Dependency injection container
└── exceptions.py           # Exception hierarchy
```

---

## Core Components

### Dependency Injection Container

All services are wired through the DI container:

```python
# src/container.py
class Container:
    """Dependency injection container following DIP."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self._instances: Dict[str, Any] = {}
    
    def get_query_pipeline_orchestrator(self) -> QueryPipelineOrchestrator:
        """Get fully wired query pipeline orchestrator."""
        return QueryPipelineOrchestrator(
            file_selector=self.get_file_selector(),
            sheet_selector=self.get_sheet_selector(),
            query_classifier=self.get_query_classifier(),
            processor_registry=self.get_processor_registry(),
            answer_generator=self.get_answer_generator(),
            trace_recorder=self.get_trace_recorder(),
            cache_service=self.get_cache_service(),
            config=self.config.query_pipeline
        )
```

### Exception Hierarchy

```python
# src/exceptions.py
class RAGSystemError(Exception):
    """Base exception for all RAG system errors."""
    pass

class ChunkViewerError(RAGSystemError):
    """Chunk viewer errors."""
    pass

class TraceError(RAGSystemError):
    """Traceability errors."""
    pass

class ClassificationError(RAGSystemError):
    """Query classification errors."""
    pass

class ProcessingError(RAGSystemError):
    """Query processing errors."""
    pass

class SelectionError(RAGSystemError):
    """File/sheet selection errors."""
    pass
```

---

## Smart Query Pipeline

### Query Pipeline Orchestrator

The central coordinator for query processing:

```python
class QueryPipelineOrchestrator:
    """
    Orchestrates the smart query pipeline.
    All dependencies injected via constructor.
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
        self.file_selector = file_selector
        self.sheet_selector = sheet_selector
        # ... all dependencies injected
    
    def process_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        file_hints: Optional[list[str]] = None
    ) -> QueryResponse:
        """Process query through full pipeline."""
        ...
```

### Query Processor Registry (OCP)

New processors can be added without modifying existing code:

```python
class QueryProcessorRegistry:
    """Registry pattern for query processors."""
    
    _processors: dict[QueryType, type[BaseQueryProcessor]] = {}
    
    @classmethod
    def register(cls, query_type: QueryType):
        """Decorator to register a processor."""
        def decorator(processor_class):
            cls._processors[query_type] = processor_class
            return processor_class
        return decorator

# Usage - registration happens in each processor module
@QueryProcessorRegistry.register(QueryType.AGGREGATION)
class AggregationProcessor(BaseQueryProcessor):
    """Processes aggregation queries."""
    
    SUPPORTED_FUNCTIONS = {"SUM", "AVERAGE", "COUNT", "MIN", "MAX", "MEDIAN"}
    
    def process(
        self,
        query: str,
        data: RetrievedData,
        classification: QueryClassification
    ) -> ProcessedResult:
        ...
```

### Adding a New Query Processor

1. Create processor in `src/query_pipeline/processors/`:

```python
# src/query_pipeline/processors/trend.py
from src.query_pipeline.processor_registry import QueryProcessorRegistry
from src.query_pipeline.processors.base import BaseQueryProcessor
from src.models.query_pipeline import QueryType

@QueryProcessorRegistry.register(QueryType.TREND)
class TrendProcessor(BaseQueryProcessor):
    """Processes trend analysis queries."""
    
    def process(
        self,
        query: str,
        data: RetrievedData,
        classification: QueryClassification
    ) -> ProcessedResult:
        # Implementation
        ...
```

2. Add QueryType enum value:

```python
# src/models/query_pipeline.py
class QueryType(str, Enum):
    AGGREGATION = "aggregation"
    LOOKUP = "lookup"
    SUMMARIZATION = "summarization"
    COMPARISON = "comparison"
    TREND = "trend"  # NEW
```

3. Update classifier keywords:

```python
# src/query_pipeline/classifier.py
TREND_KEYWORDS = {"trend", "growth", "decline", "over time", "trajectory"}
```

---

## Chunk Visibility

### ChunkViewer Service

```python
class ChunkViewer:
    """
    Provides chunk visibility and debugging capabilities.
    All dependencies injected via constructor.
    """
    
    def __init__(
        self,
        vector_store: VectorStore,
        metadata_store: ChunkMetadataStore,
        version_store: ChunkVersionStore,
        feedback_store: FeedbackStore,
        access_controller: AccessController,
        config: ChunkViewerConfig
    ) -> None:
        # All dependencies injected
        ...
    
    def get_chunks_for_file(
        self,
        file_id: str,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None
    ) -> PaginatedChunkResponse:
        """Get all chunks for a file with pagination."""
        # Check access
        if not self.access_controller.check_access(user_id, "file", file_id, "read"):
            raise AccessDeniedError(f"Access denied to file {file_id}")
        
        # Query metadata store
        chunks = self.metadata_store.get_chunks(file_id, page, page_size)
        return PaginatedChunkResponse(chunks=chunks, ...)
```

### Chunk Version Store

```python
class ChunkVersionStore:
    """Tracks chunk versions across re-indexing."""
    
    def create_version(
        self,
        file_id: str,
        chunks: list[ChunkDetails],
        extraction_strategy: str
    ) -> str:
        """Create new version when file is re-indexed."""
        ...
    
    def get_version_history(self, file_id: str) -> list[ChunkVersion]:
        """Get version history for a file."""
        ...
    
    def diff_versions(
        self,
        file_id: str,
        version_a: int,
        version_b: int
    ) -> VersionDiff:
        """Compare two versions showing added/removed/modified chunks."""
        ...
```

---

## Enterprise Features

### Access Controller

```python
class AccessController:
    """
    Role-based access control with file-level restrictions.
    Roles: admin, developer, analyst, viewer
    """
    
    def __init__(
        self,
        store: AccessControlStore,
        audit_logger: AuditLogger
    ) -> None:
        self.store = store
        self.audit_logger = audit_logger
    
    def check_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str
    ) -> bool:
        """Check if user has permission for action."""
        granted = self._check_permission(user_id, resource_type, resource_id, action)
        
        # Log access attempt
        self.audit_logger.log_access(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            granted=granted
        )
        
        return granted
```

### Batch Query Processor

```python
class BatchQueryProcessor:
    """Process multiple queries in parallel."""
    
    def __init__(
        self,
        query_pipeline: QueryPipelineOrchestrator,
        store: BatchStore,
        config: BatchConfig
    ) -> None:
        self.query_pipeline = query_pipeline
        self.store = store
        self.max_queries = config.max_queries  # Default 100
        self.parallel_workers = config.parallel_workers  # Default 5
    
    async def process_batch(
        self,
        queries: list[str],
        file_hints: Optional[list[str]] = None
    ) -> str:
        """Submit batch and return batch_id."""
        if len(queries) > self.max_queries:
            raise BatchError(f"Max {self.max_queries} queries per batch")
        
        batch_id = self._generate_batch_id()
        # Process in parallel with worker pool
        ...
        return batch_id
```

### Query Cache

```python
class QueryCache:
    """Cache query results with semantic equivalence matching."""
    
    def __init__(
        self,
        cache_service: CacheService,
        embedding_service: EmbeddingService,
        config: CacheConfig
    ) -> None:
        self.cache_service = cache_service
        self.embedding_service = embedding_service
        self.ttl = config.ttl  # Default 3600 seconds
    
    def get(self, query: str, file_ids: list[str]) -> Optional[QueryResponse]:
        """Get cached result for semantically equivalent query."""
        cache_key = self._generate_cache_key(query, file_ids)
        return self.cache_service.get(cache_key)
    
    def invalidate_for_file(self, file_id: str) -> int:
        """Invalidate all cache entries containing file_id."""
        # Called when file is re-indexed
        ...
```

---

## Adding New Features

### Adding a New API Endpoint

1. Create route in `src/api/routes/`:

```python
# src/api/routes/analytics.py
from fastapi import APIRouter, Depends
from src.api.dependencies import get_access_controller, require_authentication

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/usage")
async def get_usage_stats(
    user=Depends(require_authentication),
    access_controller=Depends(get_access_controller)
):
    # Check access
    if not access_controller.check_access(user.id, "analytics", "*", "read"):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {"queries": 100, "files": 50}
```

2. Register in main app:

```python
# src/main.py
from src.api.routes.analytics import router as analytics_router

app.include_router(analytics_router, prefix="/api/v1")
```

### Adding a New Abstraction

1. Define interface:

```python
# src/abstractions/notification_service.py
from abc import ABC, abstractmethod

class NotificationService(ABC):
    @abstractmethod
    def send(self, recipient: str, message: str) -> bool:
        """Send notification."""
        pass
```

2. Create implementations:

```python
# src/abstractions/email_notification.py
class EmailNotificationService(NotificationService):
    def __init__(self, smtp_config: SMTPConfig):
        self.smtp_config = smtp_config
    
    def send(self, recipient: str, message: str) -> bool:
        # Implementation
        ...
```

3. Register in factory:

```python
# src/abstractions/notification_factory.py
def create_notification_service(config: NotificationConfig) -> NotificationService:
    if config.provider == "email":
        return EmailNotificationService(config.smtp)
    elif config.provider == "slack":
        return SlackNotificationService(config.slack)
    raise ConfigurationError(f"Unknown provider: {config.provider}")
```

---

## Testing

### Unit Tests

```python
# tests/test_query_classifier.py
import pytest
from src.query_pipeline.classifier import QueryClassifier
from src.models.query_pipeline import QueryType

@pytest.fixture
def classifier():
    return QueryClassifier(llm_service=MockLLMService())

def test_classify_aggregation(classifier):
    result = classifier.classify("What is the total revenue?")
    assert result.query_type == QueryType.AGGREGATION
    assert result.confidence > 0.8

def test_classify_comparison(classifier):
    result = classifier.classify("Compare Q1 and Q2 sales")
    assert result.query_type == QueryType.COMPARISON
```

### Integration Tests

```python
# tests/test_query_pipeline_integration.py
import pytest
from fastapi.testclient import TestClient
from src.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_smart_query_endpoint(client, auth_token):
    response = client.post(
        "/api/v1/query/smart",
        json={"query": "What is the total revenue?"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    assert "answer" in response.json()
    assert "trace_id" in response.json()
```

---

## Configuration

### Environment Variables

```bash
# Query Pipeline
QUERY_PIPELINE_TIMEOUT=30
FILE_SELECTION_THRESHOLD_HIGH=0.9
FILE_SELECTION_THRESHOLD_LOW=0.5
CLASSIFICATION_CONFIDENCE_THRESHOLD=0.6

# Caching
QUERY_CACHE_TTL=3600
QUERY_CACHE_ENABLED=true

# Batch Processing
BATCH_MAX_QUERIES=100
BATCH_PARALLEL_WORKERS=5

# Traceability
TRACE_RETENTION_DAYS=90
ENABLE_DATA_LINEAGE=true

# Access Control
ACCESS_CONTROL_ENABLED=true
DEFAULT_USER_ROLE=viewer
AUDIT_LOG_ENABLED=true

# Extraction
EXTRACT_FORMULAS=true
EXTRACT_PIVOT_TABLES=true
QUALITY_THRESHOLD=0.5
```

---

## API Reference

See [API_ENDPOINTS_REFERENCE.md](../API_ENDPOINTS_REFERENCE.md) for complete API documentation.

Interactive documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
