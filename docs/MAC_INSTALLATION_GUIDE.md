# Mac Installation Guide

Quick setup guide for running the Google Drive Excel RAG system on macOS (Mac Pro).

## Prerequisites

- macOS 12+ (Monterey or later)
- Python 3.10+ (3.11 recommended)
- 8GB+ RAM (16GB recommended for local LLMs)
- Homebrew (optional but recommended)

## Quick Start (5 minutes)

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/GirishAh-Kore/gdrive-excel-rag.git
cd gdrive-excel-rag

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install core dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit with your settings
nano .env  # or use any editor
```

Minimum required settings:
```bash
# Google Drive (get from Google Cloud Console)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
TOKEN_ENCRYPTION_KEY=generate_32_char_key_here

# LLM (choose one)
LLM_PROVIDER=openai
LLM_API_KEY=your_openai_key
```

### 3. Run the Server

```bash
# Start the API server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000/docs for the API documentation.

---

## Configuration Options

### Option A: Cloud APIs (Easiest)

Uses OpenAI for embeddings and LLM. Requires API key but no local setup.

```bash
# .env settings
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-...
```

### Option B: Fully Local / Open-Source (No API Costs)

Run everything locally with no external API calls.

```bash
# Install additional dependencies
pip install "unstructured[xlsx]"
pip install FlagEmbedding

# For Ollama (local LLM)
brew install ollama
ollama pull llama3.1

# .env settings
EMBEDDING_PROVIDER=bge-m3
EMBEDDING_MODEL=BAAI/bge-m3
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
LLM_BASE_URL=http://localhost:11434
EXTRACTION_STRATEGY=auto
ENABLE_UNSTRUCTURED=true
```

### Option C: Hybrid (Best Performance)

Local embeddings + cloud LLM for best quality/cost balance.

```bash
# .env settings
EMBEDDING_PROVIDER=bge-m3
EMBEDDING_MODEL=BAAI/bge-m3
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-...
```

---

## Installing Open-Source Components

### BGE-M3 Embeddings (Local, Multilingual)

```bash
# Install FlagEmbedding
pip install FlagEmbedding

# Configure in .env
EMBEDDING_PROVIDER=bge-m3
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_USE_FP16=true
EMBEDDING_DEVICE=mps  # Use Apple Silicon GPU
```

First run downloads ~2GB model. Subsequent runs use cached model.

### Unstructured.io (Local Document Extraction)

```bash
# Install with Excel support
pip install "unstructured[xlsx]"

# Optional: install all document types
pip install "unstructured[all-docs]"

# Configure in .env
ENABLE_UNSTRUCTURED=true
EXTRACTION_STRATEGY=auto
```

No API key needed - runs 100% locally.

### Docling (IBM Open-Source)

```bash
# Install Docling
pip install docling

# Configure in .env
ENABLE_DOCLING=true
```

### Ollama (Local LLMs)

```bash
# Install via Homebrew
brew install ollama

# Start Ollama service
ollama serve

# Pull a model (in another terminal)
ollama pull llama3.1        # 8B params, ~4.7GB
ollama pull llama3.1:70b    # 70B params, ~40GB (needs 64GB RAM)
ollama pull mistral         # 7B params, ~4.1GB
ollama pull qwen2.5         # 7B params, ~4.4GB

# Configure in .env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
LLM_BASE_URL=http://localhost:11434
```

### vLLM (High-Performance Local LLM)

For maximum performance with local LLMs:

```bash
# Install vLLM (requires CUDA or ROCm - limited Mac support)
pip install vllm

# Start vLLM server
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-3.1-8B-Instruct \
    --port 8001

# Configure in .env
LLM_PROVIDER=vllm
LLM_MODEL=meta-llama/Llama-3.1-8B-Instruct
LLM_BASE_URL=http://localhost:8001/v1
```

Note: vLLM has limited Mac support. Use Ollama for Mac.

---

## Google Drive Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable "Google Drive API"

### 2. Create OAuth Credentials

1. Go to APIs & Services > Credentials
2. Create OAuth 2.0 Client ID
3. Application type: Desktop app (for local testing)
4. Download JSON and note the client ID/secret

### 3. Configure OAuth

```bash
# .env settings
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback
```

---

## Testing Your Installation

### 1. Health Check

```bash
curl http://localhost:8000/health
```

### 2. Test Extraction

```python
# test_extraction.py
import asyncio
from src.extraction.configurable_extractor import ConfigurableExtractor
from src.extraction.extraction_strategy import ExtractionConfig

async def test():
    config = ExtractionConfig(
        enable_unstructured=True,
        use_auto_strategy=True
    )
    extractor = ConfigurableExtractor(config)
    
    with open("test.xlsx", "rb") as f:
        result = await extractor.extract_workbook(
            f.read(), "test-id", "test.xlsx", "/test.xlsx", 
            datetime.now()
        )
    print(f"Extracted {len(result.sheets)} sheets")

asyncio.run(test())
```

### 3. Test Embeddings

```python
# test_embeddings.py
from src.abstractions.embedding_service_factory import EmbeddingServiceFactory

# Test BGE-M3
service = EmbeddingServiceFactory.create("bge-m3", model="BAAI/bge-m3")
embeddings = service.embed_texts(["Hello world", "Test query"])
print(f"Embedding dimension: {len(embeddings[0])}")  # Should be 1024
```

### 4. Test LLM

```python
# test_llm.py
import asyncio
from src.abstractions.llm_service_factory import LLMServiceFactory

async def test():
    # Test Ollama
    service = LLMServiceFactory.create(
        "ollama", 
        model="llama3.1",
        base_url="http://localhost:11434"
    )
    response = await service.generate("What is 2+2?")
    print(response)

asyncio.run(test())
```

---

## Troubleshooting

### "No module named 'unstructured'"

```bash
pip install "unstructured[xlsx]"
```

### "No module named 'FlagEmbedding'"

```bash
pip install FlagEmbedding
```

### Ollama connection refused

```bash
# Make sure Ollama is running
ollama serve

# Check if model is downloaded
ollama list
```

### Memory issues with BGE-M3

```bash
# Use FP16 to reduce memory
EMBEDDING_USE_FP16=true

# Or use smaller model
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
```

### Apple Silicon (M1/M2/M3) GPU acceleration

```bash
# For PyTorch/BGE-M3
EMBEDDING_DEVICE=mps

# For Ollama - automatic GPU detection
```

---

## Recommended Mac Pro Configuration

For a Mac Pro with 32GB+ RAM:

```bash
# .env - Optimal local setup
EMBEDDING_PROVIDER=bge-m3
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_USE_FP16=true
EMBEDDING_DEVICE=mps

LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
LLM_BASE_URL=http://localhost:11434

EXTRACTION_STRATEGY=auto
ENABLE_UNSTRUCTURED=true

VECTOR_STORE_PROVIDER=chromadb
CHROMA_PERSIST_DIR=./chroma_db
```

This gives you:
- Fast local embeddings with Apple Silicon GPU
- Quality local LLM responses
- Smart extraction with pivot table support
- No API costs
