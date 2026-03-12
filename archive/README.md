# Google Drive Excel RAG System

A Retrieval-Augmented Generation (RAG) application that connects to Google Drive, indexes Excel files, and answers user questions using natural language queries.

## Features

- OAuth 2.0 authentication with Google Drive
- Recursive indexing of Excel files across folders
- Support for .xlsx, .xls, and .xlsm formats
- Formula, pivot table, and chart extraction
- Semantic search using vector embeddings
- Natural language query processing
- Cross-file comparison capabilities
- Pluggable architecture for vector stores, embeddings, and LLMs

## Setup

### Prerequisites

- Python 3.9 or higher
- Google Cloud Project with Drive API enabled
- API keys for chosen providers (OpenAI, Anthropic, etc.)

### Installation

1. Clone the repository and navigate to the project directory

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Drive API
4. Create OAuth 2.0 credentials (Desktop app)
5. Download credentials and add to .env file

## Usage

### CLI Commands

**Authentication:**
```bash
python -m src.cli auth login
python -m src.cli auth status
python -m src.cli auth logout
```

**Indexing:**
```bash
python -m src.cli index full
python -m src.cli index incremental
python -m src.cli index status
```

**Querying:**
```bash
python -m src.cli query "What was the total expense in January?"
```

### API Server

Start the FastAPI server:
```bash
uvicorn src.main:app --reload
```

Access API documentation at: http://localhost:8000/docs

## Architecture

The system uses a modular architecture with pluggable abstractions:

- **Vector Stores**: ChromaDB (MVP) or OpenSearch (production)
- **Embeddings**: OpenAI, Sentence Transformers, or Cohere
- **LLMs**: OpenAI GPT, Anthropic Claude, or Google Gemini

## Configuration

All configuration is managed through environment variables. See `.env.example` for available options.

## Vector Store Migration

The system supports migrating data between different vector store implementations (e.g., ChromaDB to OpenSearch for production scaling).

**Quick Migration:**
```bash
# ChromaDB to OpenSearch
python scripts/migrate_vector_store.py --source chromadb --target opensearch

# Rollback if needed
python scripts/migrate_vector_store.py --source opensearch --target chromadb --rollback
```

**Features:**
- Automatic backup creation
- Data validation
- Rollback capability
- Batch processing for large datasets

See [docs/MIGRATION.md](docs/MIGRATION.md) for detailed migration guide.

## Development

Run tests:
```bash
pytest tests/
```

## License

MIT

## Documentation

- **[User Guide](docs/USER_GUIDE.md)** - End-user documentation for using the system
- **[Developer Guide](docs/DEVELOPER_GUIDE.md)** - Technical documentation for developers
- **[Solution Architecture](SOLUTION_ARCHITECTURE.md)** - Comprehensive system architecture
- **[API Reference](API_ENDPOINTS_REFERENCE.md)** - Complete API documentation
- **[Docker Deployment](DOCKER.md)** - Docker deployment guide
- **[Docker Quick Start](DOCKER_QUICK_START.md)** - Quick start for Docker
- **[Migration Guide](docs/MIGRATION.md)** - Vector store migration guide
