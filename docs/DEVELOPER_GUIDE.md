# Google Drive Excel RAG System - Developer Guide

Technical documentation for developers working on or integrating with the system.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Development Setup](#development-setup)
3. [Project Structure](#project-structure)
4. [Core Components](#core-components)
5. [Adding New Features](#adding-new-features)
6. [Testing](#testing)
7. [Deployment](#deployment)
8. [API Reference](#api-reference)
9. [Configuration](#configuration)
10. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

The system follows a modular, layered architecture with pluggable abstractions:

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│              (React Frontend + FastAPI REST)                 │
├─────────────────────────────────────────────────────────────┤
│                    Application Layer                         │
│     (Query Engine, Indexing Pipeline, Auth Service)          │
├─────────────────────────────────────────────────────────────┤
│                    Domain Layer                              │
│        (Domain Models, Business Logic, Validators)           │
├─────────────────────────────────────────────────────────────┤
│                    Infrastructure Layer                      │
│   (Vector Store, Database, Cache, External APIs)             │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Dependency Injection** - Services are injected via FastAPI dependencies
2. **Factory Pattern** - Pluggable implementations for vector stores, embeddings, LLMs
3. **Strategy Pattern** - Configurable extraction strategies
4. **Repository Pattern** - Data access abstracted through storage classes

---

## Development Setup

### Prerequisites

- Python 3.9+
- Node.js 20.19+ or 22.12+
- Docker (optional, for containerized development)

### Backend Setup

```bash
# Clone repository
git clone <repository-url>
cd gdrive-excel-rag

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Copy environment template
cp .env.example .env
# Edit .env with your credentials

# Run database migrations
python -c "from src.database.migrations import run_migrations; run_migrations()"

# Start development server
uvicorn src.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment template
cp .env.example .env

# Start development server
npm run dev
```

### Running Tests

```bash
# Backend tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Frontend tests
cd frontend && npm test
```

---

## Project Structure

```
gdrive-excel-rag/
├── src/                          # Backend source code
│   ├── abstractions/             # Pluggable service abstractions
│   │   ├── vector_store.py       # Vector store interface
│   │   ├── chromadb_store.py     # ChromaDB implementation
│   │   ├── opensearch_store.py   # OpenSearch implementation
│   │   ├── embedding_service.py  # Embedding interface
│   │   ├── openai_embedding_service.py
│   │   ├── sentence_transformer_service.py
│   │   ├── cohere_embedding_service.py
│   │   ├── bge_embedding_service.py  # BGE-M3 (local, multilingual)
│   │   ├── llm_service.py        # LLM interface
│   │   ├── openai_llm_service.py
│   │   ├── anthropic_llm_service.py
│   │   ├── gemini_llm_service.py
│   │   ├── ollama_llm_service.py     # Ollama (local)
│   │   ├── vllm_llm_service.py       # vLLM server
│   │   ├── cache_service.py      # Cache interface
│   │   ├── memory_cache.py
│   │   └── redis_cache.py
│   ├── api/                      # FastAPI routes and models
│   │   ├── auth.py               # Google Drive OAuth
│   │   ├── web_auth.py           # Web app JWT auth
│   │   ├── files.py              # File management
│   │   ├── chat.py               # Chat sessions
│   │   ├── indexing.py           # Indexing operations
│   │   ├── query.py              # Query processing
│   │   ├── models.py             # Pydantic models
│   │   ├── middleware.py         # Request middleware
│   │   └── dependencies.py       # Dependency injection
│   ├── auth/                     # Authentication layer
│   │   ├── oauth_flow.py         # OAuth 2.0 flow
│   │   ├── token_storage.py      # Encrypted token storage
│   │   ├── token_refresh.py      # Token refresh logic
│   │   └── authentication_service.py
│   ├── gdrive/                   # Google Drive integration
│   │   └── connector.py          # Drive API client
│   ├── extraction/               # Excel extraction
│   │   ├── content_extractor.py  # Core extraction (openpyxl)
│   │   ├── configurable_extractor.py
│   │   ├── sheet_summarizer.py
│   │   ├── extraction_strategy.py
│   │   ├── docling_extractor.py  # IBM Docling (open-source)
│   │   ├── unstructured_extractor.py  # Unstructured.io (open-source)
│   │   ├── gemini_extractor.py   # Google Gemini
│   │   └── llama_extractor.py    # LlamaParse
│   ├── indexing/                 # Indexing pipeline
│   │   ├── indexing_pipeline.py
│   │   ├── indexing_orchestrator.py
│   │   ├── embedding_generator.py
│   │   ├── vector_storage.py
│   │   └── metadata_storage.py
│   ├── query/                    # Query processing
│   │   ├── query_engine.py       # Main orchestrator
│   │   ├── query_analyzer.py     # Intent extraction
│   │   ├── semantic_searcher.py  # Vector search
│   │   ├── hybrid_searcher.py    # BM25 + semantic fusion
│   │   ├── reranker.py           # Cross-encoder reranking
│   │   ├── query_expander.py     # HyDE query expansion
│   │   ├── context_compressor.py # Contextual compression
│   │   ├── file_selector.py      # File ranking
│   │   ├── sheet_selector.py     # Sheet selection
│   │   ├── comparison_engine.py  # Cross-file comparison
│   │   ├── answer_generator.py   # LLM answer generation
│   │   ├── confidence_scorer.py
│   │   ├── citation_generator.py
│   │   └── conversation_manager.py
│   ├── text_processing/          # Multi-language support
│   │   ├── language_detector.py
│   │   ├── tokenizer.py
│   │   ├── normalizer.py
│   │   └── preprocessor.py
│   ├── database/                 # Database layer
│   │   ├── connection.py
│   │   ├── schema.py
│   │   └── migrations.py
│   ├── models/                   # Domain models
│   │   └── domain_models.py
│   ├── utils/                    # Utilities
│   │   ├── logging_config.py
│   │   ├── metrics.py
│   │   └── dependency_checker.py
│   ├── config.py                 # Configuration management
│   ├── cli.py                    # CLI interface
│   └── main.py                   # FastAPI application
├── frontend/                     # React frontend
│   ├── src/
│   │   ├── components/           # React components
│   │   ├── pages/                # Page components
│   │   ├── services/             # API services
│   │   ├── hooks/                # Custom hooks
│   │   ├── types/                # TypeScript types
│   │   └── utils/                # Utilities
│   └── ...
├── tests/                        # Test suite
├── examples/                     # Usage examples
├── scripts/                      # Utility scripts
├── docs/                         # Documentation
└── ...
```

---

## Core Components

### Vector Store Abstraction

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class VectorStore(ABC):
    @abstractmethod
    def create_collection(self, name: str, dimension: int, 
                         metadata_schema: Optional[Dict] = None) -> bool:
        """Create a new collection."""
        pass
    
    @abstractmethod
    def add_embeddings(self, collection: str, ids: List[str],
                      embeddings: List[List[float]], 
                      documents: List[str],
                      metadata: List[Dict]) -> bool:
        """Add embeddings to collection."""
        pass
    
    @abstractmethod
    def search(self, collection: str, query_embedding: List[float],
              top_k: int = 10, filters: Optional[Dict] = None) -> List[Dict]:
        """Search for similar embeddings."""
        pass
```

### Embedding Service Abstraction

```python
class EmbeddingService(ABC):
    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """Return embedding dimension."""
        pass
    
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch of texts."""
        pass
```

### LLM Service Abstraction

```python
class LLMService(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                temperature: float = 0.7, max_tokens: int = 1000) -> str:
        """Generate text response."""
        pass
    
    @abstractmethod
    def generate_structured(self, prompt: str, response_schema: Dict,
                           system_prompt: Optional[str] = None) -> Dict:
        """Generate structured JSON response."""
        pass
```

### Dependency Injection

```python
# src/api/dependencies.py

from functools import lru_cache
from src.config import AppConfig
from src.abstractions.vector_store_factory import create_vector_store
from src.abstractions.embedding_service_factory import create_embedding_service
from src.abstractions.llm_service_factory import create_llm_service

@lru_cache()
def get_app_config() -> AppConfig:
    return AppConfig()

def get_vector_store():
    config = get_app_config()
    return create_vector_store(config.vector_store)

def get_embedding_service():
    config = get_app_config()
    return create_embedding_service(config.embedding)

def get_llm_service():
    config = get_app_config()
    return create_llm_service(config.llm)
```

---

## Adding New Features

### Adding a New Vector Store

1. Create implementation in `src/abstractions/`:

```python
# src/abstractions/pinecone_store.py
from src.abstractions.vector_store import VectorStore

class PineconeStore(VectorStore):
    def __init__(self, api_key: str, environment: str):
        import pinecone
        pinecone.init(api_key=api_key, environment=environment)
        self.index = None
    
    def create_collection(self, name, dimension, metadata_schema=None):
        # Implementation
        pass
    
    # ... implement other methods
```

2. Register in factory:

```python
# src/abstractions/vector_store_factory.py
def create_vector_store(config: VectorStoreConfig) -> VectorStore:
    if config.provider == "pinecone":
        from src.abstractions.pinecone_store import PineconeStore
        return PineconeStore(config.api_key, config.environment)
    # ... existing providers
```

3. Add configuration:

```python
# src/config.py
class VectorStoreConfig:
    provider: str  # "chromadb", "opensearch", "pinecone"
    # ... add pinecone-specific config
```

### Adding a New Embedding Provider

1. Create implementation:

```python
# src/abstractions/voyage_embedding_service.py
from src.abstractions.embedding_service import EmbeddingService

class VoyageEmbeddingService(EmbeddingService):
    def __init__(self, api_key: str, model: str = "voyage-2"):
        import voyageai
        self.client = voyageai.Client(api_key=api_key)
        self.model = model
    
    def get_embedding_dimension(self) -> int:
        return 1024  # voyage-2 dimension
    
    def embed_text(self, text: str) -> List[float]:
        result = self.client.embed([text], model=self.model)
        return result.embeddings[0]
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        result = self.client.embed(texts, model=self.model)
        return result.embeddings
```

2. Register in factory and update config.

### Adding a New API Endpoint

1. Create router:

```python
# src/api/analytics.py
from fastapi import APIRouter, Depends
from src.api.dependencies import require_authentication

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/usage")
async def get_usage_stats(user=Depends(require_authentication)):
    # Implementation
    return {"queries": 100, "files": 50}
```

2. Register in main app:

```python
# src/main.py
from src.api.analytics import router as analytics_router

app.include_router(analytics_router, prefix="/api/v1")
```

---

## Testing

### Unit Tests

```python
# tests/test_query_analyzer.py
import pytest
from src.query.query_analyzer import QueryAnalyzer

@pytest.fixture
def analyzer():
    return QueryAnalyzer(llm_service=MockLLMService())

def test_extract_intent(analyzer):
    result = analyzer.analyze("What was the total revenue?")
    assert result.intent == "retrieve"
    assert "revenue" in result.entities

def test_detect_comparison(analyzer):
    result = analyzer.analyze("Compare Q1 and Q2 sales")
    assert result.intent == "compare"
    assert result.comparison_detected
```

### Integration Tests

```python
# tests/test_integration.py
import pytest
from fastapi.testclient import TestClient
from src.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_query_endpoint(client, auth_token):
    response = client.post(
        "/api/v1/query",
        json={"query": "What is the total?"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    assert "answer" in response.json()
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/test_query_analyzer.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Skip slow tests
pytest tests/ -v -m "not slow"
```

---

## Deployment

### Docker Deployment

```bash
# Build and start
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Production Checklist

- [ ] Change default credentials
- [ ] Generate strong JWT and encryption keys
- [ ] Configure HTTPS via reverse proxy
- [ ] Set up monitoring and alerting
- [ ] Configure automated backups
- [ ] Review rate limits
- [ ] Set resource limits
- [ ] Enable structured logging
- [ ] Configure CORS origins

### Scaling Considerations

| Component | MVP | Production |
|-----------|-----|------------|
| Vector Store | ChromaDB (local) | OpenSearch (cluster) |
| Cache | In-memory | Redis (cluster) |
| Database | SQLite | PostgreSQL |
| Workers | Single process | Multiple instances |

---

## API Reference

See `API_ENDPOINTS_REFERENCE.md` for complete API documentation.

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Web authentication |
| POST | `/api/v1/query` | Submit query |
| POST | `/api/v1/files/upload` | Upload file |
| GET | `/api/v1/files/list` | List files |
| POST | `/api/v1/index/full` | Full indexing |
| GET | `/health` | Health check |

---

## Configuration

### Environment Variables

See `.env.example` for all available options.

### Key Configuration Sections

```bash
# Vector Store
VECTOR_STORE_PROVIDER=chromadb  # or opensearch
CHROMADB_PATH=./data/chroma

# Embedding (choose one)
EMBEDDING_PROVIDER=openai       # OpenAI (API)
EMBEDDING_PROVIDER=bge-m3       # BGE-M3 (local, free)
EMBEDDING_PROVIDER=sentence-transformers  # Local, free
EMBEDDING_API_KEY=sk-...        # Only for API providers
EMBEDDING_MODEL=text-embedding-3-small

# LLM (choose one)
LLM_PROVIDER=openai             # OpenAI GPT-4o
LLM_PROVIDER=anthropic          # Claude 3.5 Sonnet
LLM_PROVIDER=gemini             # Google Gemini
LLM_PROVIDER=ollama             # Ollama (local, free)
LLM_PROVIDER=vllm               # vLLM server
LLM_API_KEY=sk-...              # Only for API providers
LLM_MODEL=gpt-4o
LLM_BASE_URL=http://localhost:11434  # For Ollama/vLLM

# Extraction Strategy
EXTRACTION_STRATEGY=openpyxl    # Best for pivot tables/charts
EXTRACTION_STRATEGY=unstructured  # Open-source, local
EXTRACTION_STRATEGY=docling     # IBM open-source

# Advanced RAG Features
ENABLE_HYBRID_SEARCH=true       # BM25 + semantic
ENABLE_RERANKING=true           # Cross-encoder reranking
ENABLE_HYDE=true                # HyDE query expansion
ENABLE_STREAMING=true           # SSE streaming

# Cache
CACHE_BACKEND=memory            # or redis
REDIS_HOST=localhost

# Language
SUPPORTED_LANGUAGES=en,th
DEFAULT_LANGUAGE=en
```

---

## Troubleshooting

### Common Development Issues

**Import errors:**
```bash
# Ensure you're in the virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

**Database locked:**
```bash
# Stop all processes using the database
# Delete the lock file if present
rm -f data/metadata.db-journal
```

**Vector store connection failed:**
```bash
# Check ChromaDB is running
curl http://localhost:8001/api/v1/heartbeat

# Restart ChromaDB
docker-compose restart chromadb
```

### Debugging Tips

1. Enable debug logging:
```bash
LOG_LEVEL=DEBUG uvicorn src.main:app --reload
```

2. Use correlation IDs to trace requests through logs

3. Check health endpoint for component status:
```bash
curl http://localhost:8000/health | jq
```

4. Use interactive API docs at `/docs` for testing

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

### Code Style

- Python: Follow PEP 8, use type hints
- TypeScript: Follow ESLint configuration
- Use meaningful variable and function names
- Add docstrings to public functions
- Keep functions focused and small

