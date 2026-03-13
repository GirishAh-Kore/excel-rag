# Excel RAG System

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready Retrieval-Augmented Generation (RAG) system for querying Excel files using natural language. Connect to Google Drive, index your spreadsheets, and get intelligent answers with source citations and full traceability.

## Features

- **Natural Language Queries** - Ask questions in plain English (or Thai) about your Excel data
- **Smart Query Pipeline** - Intelligent file/sheet selection, query classification, and answer generation
- **Google Drive Integration** - OAuth 2.0 authentication with automatic file discovery
- **Advanced RAG Pipeline** - Hybrid search (BM25 + semantic), cross-encoder reranking, HyDE query expansion
- **Chunk Visibility** - Debug and inspect indexed data with version tracking
- **Enterprise Features** - Access control, batch processing, templates, webhooks, export
- **Full Traceability** - Complete audit trail from query to answer with data lineage
- **Multi-Provider Support** - Pluggable LLMs, embeddings, and vector stores
- **Open-Source Options** - Run fully locally with Ollama, BGE-M3, and ChromaDB (zero API costs)
- **Excel Intelligence** - Extracts formulas, pivot tables, charts, and complex structures
- **Cross-File Comparison** - Compare data across multiple spreadsheets
- **Multi-Language** - English and Thai with automatic language detection

## Quick Start

### Option 1: Automated Setup (Recommended)

```bash
# Clone the repository
git clone https://github.com/GirishAh-Kore/excel-rag.git
cd excel-rag

# Run the setup script
./scripts/setup-local.sh

# Follow the printed instructions to start the services
```

### Option 2: Manual Setup

```bash
# Clone the repository
git clone https://github.com/GirishAh-Kore/excel-rag.git
cd excel-rag

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install FlagEmbedding  # For local embeddings

# Configure environment (use local config - no API keys needed)
cp .env.local .env
```

### Start the Services

```bash
# Terminal 1: Start Ollama (local LLM)
brew install ollama  # First time only
ollama pull llama3.1  # First time only
ollama serve

# Terminal 2: Start Backend
source venv/bin/activate
uvicorn src.main:app --reload --port 8000

# Terminal 3: Start Frontend
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 and login with `girish` / `Girish@123`

📖 **Detailed Guide**: See [Installation Guide](docs/INSTALLATION_GUIDE.md) for complete setup instructions.

📖 **Mac Users**: See [Mac Installation Guide](docs/MAC_INSTALLATION_GUIDE.md) for Apple Silicon optimization.

## Configuration Options

The system is highly configurable through environment variables.

### LLM Providers

| Provider | Config | Notes |
|----------|--------|-------|
| OpenAI | `LLM_PROVIDER=openai` | GPT-4o, GPT-4o-mini |
| Anthropic | `LLM_PROVIDER=anthropic` | Claude 3.5 Sonnet, Claude 3 Opus |
| Google Gemini | `LLM_PROVIDER=gemini` | Gemini Pro, Gemini 1.5 Flash |
| Ollama | `LLM_PROVIDER=ollama` | Llama 3.1, Mistral, Qwen (local, free) |
| vLLM | `LLM_PROVIDER=vllm` | Any HuggingFace model via vLLM server |

### Embedding Providers

| Provider | Config | Dimensions | Notes |
|----------|--------|------------|-------|
| OpenAI | `EMBEDDING_PROVIDER=openai` | 1536/3072 | text-embedding-3-small/large |
| Sentence Transformers | `EMBEDDING_PROVIDER=sentence-transformers` | 384/768 | Local, free |
| Cohere | `EMBEDDING_PROVIDER=cohere` | 1024 | embed-english-v3.0 |
| BGE-M3 | `EMBEDDING_PROVIDER=bge-m3` | 1024 | Multilingual, local, free |

### Extraction Strategies

| Strategy | Config | Best For |
|----------|--------|----------|
| openpyxl | `EXTRACTION_STRATEGY=openpyxl` | **Pivot tables & charts** (recommended) |
| Unstructured | `EXTRACTION_STRATEGY=unstructured` | Complex layouts, runs locally |
| Docling | `EXTRACTION_STRATEGY=docling` | PDF-heavy workflows |
| Gemini | `EXTRACTION_STRATEGY=gemini` | Multimodal understanding |

### Vector Stores

| Store | Config | Use Case |
|-------|--------|----------|
| ChromaDB | `VECTOR_STORE_PROVIDER=chromadb` | Development, MVP |
| OpenSearch | `VECTOR_STORE_PROVIDER=opensearch` | Production, scaling |

## Example Configurations

### Fully Open-Source (Zero API Costs)
```bash
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
LLM_BASE_URL=http://localhost:11434
EMBEDDING_PROVIDER=bge-m3
EMBEDDING_MODEL=BAAI/bge-m3
VECTOR_STORE_PROVIDER=chromadb
EXTRACTION_STRATEGY=openpyxl
```

### Cloud Configuration (OpenAI + ChromaDB)
```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-...
VECTOR_STORE_PROVIDER=chromadb
```

## Advanced RAG Features

| Feature | Config | Description |
|---------|--------|-------------|
| Hybrid Search | `ENABLE_HYBRID_SEARCH=true` | BM25 + semantic search with RRF fusion |
| Cross-Encoder Reranking | `ENABLE_RERANKING=true` | Rerank results with cross-encoder model |
| HyDE Query Expansion | `ENABLE_HYDE=true` | Hypothetical Document Embeddings |
| Streaming Responses | `ENABLE_STREAMING=true` | SSE streaming for long answers |
| Query Caching | `QUERY_CACHE_ENABLED=true` | Cache results with configurable TTL |

## Smart Query Pipeline (NEW)

The system includes an intelligent query pipeline that:

1. **Classifies Queries** - Automatically detects query type (aggregation, lookup, summarization, comparison)
2. **Selects Files** - Ranks files by semantic similarity, metadata matching, and user preferences
3. **Selects Sheets** - Identifies the most relevant sheets within selected files
4. **Generates Answers** - Produces natural language answers with source citations
5. **Tracks Lineage** - Records complete data path from source cells to answers

### Query Types

| Type | Example | Processing |
|------|---------|------------|
| Aggregation | "What is the total revenue?" | SUM, AVG, COUNT, MIN, MAX, MEDIAN |
| Lookup | "Show me Q1 expenses" | Find specific values with formatting |
| Summarization | "Summarize the sales data" | Generate natural language summary |
| Comparison | "Compare Q1 vs Q2" | Calculate differences and trends |

## Enterprise Features (NEW)

### Chunk Visibility
- View all indexed chunks with metadata
- Search chunks with semantic similarity
- Track chunk versions across re-indexing
- Submit feedback on chunk quality

### Traceability
- Complete audit trail for every query
- Data lineage from source cell to answer
- Configurable retention (default 90 days)
- Export traces in JSON/CSV

### Access Control
- Role-based access (admin, developer, analyst, viewer)
- File-level permissions
- Audit logging for all access attempts

### Batch Processing
- Process up to 100 queries in parallel
- Progress tracking via batch_id
- Continue on partial failures

### Query Templates
- Parameterized templates with `{{parameter}}` syntax
- Share templates within organization
- Execute with parameter substitution

### Webhooks
- Events: indexing_complete, query_failed, low_confidence_answer, batch_complete
- Retry with exponential backoff
- Delivery history tracking

### Export
- Formats: CSV, Excel (.xlsx), JSON
- Preserve data types and formatting
- Scheduled exports for recurring reports

## CLI Usage

```bash
# Authentication
python -m src.cli auth login
python -m src.cli auth status

# Indexing
python -m src.cli index full
python -m src.cli index incremental
python -m src.cli index status

# Querying
python -m src.cli query "What was the total revenue in Q1?"
```

## API Endpoints

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/query` | Submit natural language query |
| POST | `/api/v1/query/stream` | Streaming query response (SSE) |
| POST | `/api/v1/files/upload` | Upload Excel file |
| GET | `/api/v1/files/list` | List indexed files |
| POST | `/api/v1/index/full` | Start full indexing |
| GET | `/health` | Health check |

### Smart Query Pipeline (NEW)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/query/smart` | Process with smart pipeline |
| POST | `/api/v1/query/clarify` | Respond to clarification |
| GET | `/api/v1/query/classify` | Get query classification |
| GET | `/api/v1/query/trace/{trace_id}` | Get query trace |
| GET | `/api/v1/lineage/{lineage_id}` | Get data lineage |

### Chunk Visibility (NEW)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/chunks/{file_id}` | Get chunks for file |
| POST | `/api/v1/chunks/search` | Search chunks |
| GET | `/api/v1/files/{file_id}/extraction-metadata` | Get extraction details |
| GET | `/api/v1/files/quality-report` | Get quality scores |

### Enterprise (NEW)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/query/batch` | Submit batch queries |
| POST | `/api/v1/query/templates` | Create query template |
| POST | `/api/v1/export` | Export results |
| POST | `/api/v1/webhooks` | Register webhook |

See full API documentation at `/docs` when the server is running.

## Docker Deployment

```bash
# Build and start
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Project Structure

```
excel-rag/
├── src/
│   ├── abstractions/      # Pluggable services (LLM, embedding, vector store)
│   ├── access_control/    # Role-based access control (NEW)
│   ├── api/               # FastAPI routes
│   │   └── routes/        # Modular API routes (NEW)
│   ├── auth/              # OAuth 2.0 authentication
│   ├── batch/             # Batch query processing (NEW)
│   ├── cache/             # Query caching (NEW)
│   ├── chunk_viewer/      # Chunk visibility (NEW)
│   ├── export/            # Export service (NEW)
│   ├── extraction/        # Excel extraction strategies
│   ├── gdrive/            # Google Drive integration
│   ├── indexing/          # Indexing pipeline
│   ├── intelligence/      # Date parsing, anomaly detection (NEW)
│   ├── models/            # Domain models (NEW)
│   ├── query/             # Query processing engine
│   ├── query_pipeline/    # Smart query pipeline (NEW)
│   ├── templates/         # Query templates (NEW)
│   ├── text_processing/   # Multi-language support
│   ├── traceability/      # Audit and lineage (NEW)
│   ├── webhooks/          # Webhook system (NEW)
│   └── config.py          # Configuration management
├── frontend/              # React frontend
├── tests/                 # Test suite
└── docs/                  # Documentation
```

## Documentation

- [User Guide](docs/USER_GUIDE.md) - End-user documentation
- [Developer Guide](docs/DEVELOPER_GUIDE.md) - Technical documentation
- [Solution Architecture](SOLUTION_ARCHITECTURE.md) - System architecture
- [API Reference](API_ENDPOINTS_REFERENCE.md) - Complete API docs
- [Docker Guide](DOCKER.md) - Docker deployment
- [Installation Guide](docs/INSTALLATION_GUIDE.md) - Setup instructions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Submit a pull request

## License

MIT
