# Excel RAG System

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready Retrieval-Augmented Generation (RAG) system for querying Excel files using natural language. Connect to Google Drive, index your spreadsheets, and get intelligent answers with source citations.

## Features

- **Natural Language Queries** - Ask questions in plain English (or Thai) about your Excel data
- **Google Drive Integration** - OAuth 2.0 authentication with automatic file discovery
- **Advanced RAG Pipeline** - Hybrid search (BM25 + semantic), cross-encoder reranking, HyDE query expansion
- **Multi-Provider Support** - Pluggable LLMs, embeddings, and vector stores
- **Open-Source Options** - Run fully locally with Ollama, BGE-M3, and ChromaDB (zero API costs)
- **Excel Intelligence** - Extracts formulas, pivot tables, charts, and complex structures
- **Cross-File Comparison** - Compare data across multiple spreadsheets
- **Multi-Language** - English and Thai with automatic language detection

## Quick Start

### Prerequisites

- Python 3.9+
- Google Cloud Project with Drive API enabled (for Google Drive integration)

### Installation

```bash
# Clone the repository
git clone https://github.com/GirishAh-Kore/excel-rag.git
cd excel-rag

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Start the Server

```bash
uvicorn src.api.main:app --reload
```

📖 **Mac Users**: See [Mac Installation Guide](docs/MAC_INSTALLATION_GUIDE.md) for detailed setup with Apple Silicon optimization.

Access the API at http://localhost:8000 and documentation at http://localhost:8000/docs

## Configuration Options

The system is highly configurable through environment variables. Here are the key options:

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
| openpyxl | `EXTRACTION_STRATEGY=openpyxl` | **Pivot tables & charts** (recommended default) |
| Unstructured | `EXTRACTION_STRATEGY=unstructured` | Complex layouts, runs locally |
| Docling | `EXTRACTION_STRATEGY=docling` | PDF-heavy workflows |
| Gemini | `EXTRACTION_STRATEGY=gemini` | Multimodal understanding |

> **Note**: openpyxl is recommended for Excel files with pivot tables and charts. Unstructured and Docling flatten pivot tables and ignore charts.

### Vector Stores

| Store | Config | Use Case |
|-------|--------|----------|
| ChromaDB | `VECTOR_STORE_PROVIDER=chromadb` | Development, MVP |
| OpenSearch | `VECTOR_STORE_PROVIDER=opensearch` | Production, scaling |

## Example Configurations

### Cloud Configuration (OpenAI + ChromaDB)
```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-...
VECTOR_STORE_PROVIDER=chromadb
```

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

### High-Performance Local (vLLM)
```bash
LLM_PROVIDER=vllm
LLM_MODEL=meta-llama/Llama-3.1-8B-Instruct
LLM_BASE_URL=http://localhost:8000/v1
EMBEDDING_PROVIDER=bge-m3
VECTOR_STORE_PROVIDER=chromadb
```

## Advanced RAG Features

The system includes modern RAG improvements that can be toggled:

| Feature | Config | Description |
|---------|--------|-------------|
| Hybrid Search | `ENABLE_HYBRID_SEARCH=true` | BM25 + semantic search with RRF fusion |
| Cross-Encoder Reranking | `ENABLE_RERANKING=true` | Rerank results with cross-encoder model |
| HyDE Query Expansion | `ENABLE_HYDE=true` | Hypothetical Document Embeddings |
| Streaming Responses | `ENABLE_STREAMING=true` | SSE streaming for long answers |
| Split Models | `ANALYSIS_MODEL` / `GENERATION_MODEL` | Use different models for analysis vs generation |

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

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/query` | Submit natural language query |
| POST | `/api/v1/query/stream` | Streaming query response (SSE) |
| POST | `/api/v1/files/upload` | Upload Excel file |
| GET | `/api/v1/files/list` | List indexed files |
| POST | `/api/v1/index/full` | Start full indexing |
| GET | `/api/v1/index/status/{job_id}` | Check indexing status |
| GET | `/health` | Health check |

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
│   ├── api/               # FastAPI routes
│   ├── auth/              # OAuth 2.0 authentication
│   ├── extraction/        # Excel extraction strategies
│   ├── gdrive/            # Google Drive integration
│   ├── indexing/          # Indexing pipeline
│   ├── query/             # Query processing engine
│   ├── text_processing/   # Multi-language support
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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Submit a pull request

## License

MIT
