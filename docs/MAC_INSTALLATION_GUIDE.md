# Mac Installation Guide

Quick setup guide for running the Google Drive Excel RAG system on macOS (Mac Pro).

## Prerequisites

- macOS 12+ (Monterey or later)
- Python 3.10+ (3.11 recommended)
- 8GB+ RAM (16GB recommended for local LLMs)
- Homebrew (optional but recommended)

## Quick Start - Fully Local (5 minutes)

This setup runs everything locally with no API costs and no external services.

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

# Install BGE-M3 for local embeddings
pip install FlagEmbedding
```

### 2. Install Ollama (Local LLM)

```bash
# Install Ollama
brew install ollama

# Pull the Llama 3.1 model (~4.7GB download, one-time)
ollama pull llama3.1
```

### 3. Configure Environment

```bash
# Use the pre-configured local settings
cp .env.local .env
```

That's it! The `.env.local` file has sensible defaults for local development.

### 4. Start the Services

You need 3 terminal windows:

**Terminal 1 - Ollama (LLM server):**
```bash
ollama serve
```

**Terminal 2 - Backend API:**
```bash
cd ~/Downloads/Personal/Kiro-AnswerFromExcel  # or your project path
source venv/bin/activate
uvicorn src.main:app --reload --port 8000
```

**Terminal 3 - Frontend:**
```bash
cd frontend
npm install  # first time only
npm run dev
```

### 5. Use the App

1. Open http://localhost:5173 in your browser
2. Login with: `girish` / `Girish@123`
3. Drag & drop an Excel file to upload
4. Wait for indexing (watch Terminal 2 for progress)
5. Ask questions in the chat!

---

## What Runs Where?

| Component | How it runs | Service needed? |
|-----------|-------------|-----------------|
| BGE-M3 Embeddings | In-process (Python) | No - downloads model on first use |
| ChromaDB | In-process (Python) | No - saves to ./chroma_db folder |
| Ollama LLM | Separate process | Yes - run `ollama serve` |
| Backend API | Separate process | Yes - run `uvicorn` |
| Frontend | Separate process | Yes - run `npm run dev` |

**First run notes:**
- BGE-M3 model downloads ~2GB on first embedding call
- This happens automatically, just wait for it to complete
- Subsequent runs use the cached model
