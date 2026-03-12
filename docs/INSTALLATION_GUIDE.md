# Installation & Setup Guide

Complete guide for installing and running the Excel RAG System locally. This guide covers setup for macOS, with notes for Linux/Windows where applicable.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (5 Minutes)](#quick-start-5-minutes)
3. [Detailed Installation Steps](#detailed-installation-steps)
4. [Running the Application](#running-the-application)
5. [Using the Application](#using-the-application)
6. [Configuration Options](#configuration-options)
7. [Troubleshooting](#troubleshooting)
8. [Architecture Overview](#architecture-overview)

---

## Prerequisites

### Required Software

| Software | Version | Purpose | Installation |
|----------|---------|---------|--------------|
| Python | 3.10+ (3.11 recommended) | Backend runtime | `brew install python@3.11` |
| Node.js | 18+ | Frontend build | `brew install node` |
| Git | Any recent | Clone repository | `brew install git` |

### Hardware Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| RAM | 8GB | 16GB+ |
| Disk Space | 10GB | 20GB (for models) |
| CPU | Any modern | Apple Silicon (M1/M2/M3) for GPU acceleration |

### Optional Software

| Software | Purpose | When Needed |
|----------|---------|-------------|
| Homebrew | Package manager (macOS) | Makes installation easier |
| Ollama | Local LLM | For fully local setup (no API costs) |

---

## Quick Start (5 Minutes)

For those who want to get up and running quickly:

```bash
# 1. Clone the repository
git clone https://github.com/GirishAh-Kore/excel-rag.git
cd excel-rag

# 2. Run the setup script (creates venv, installs deps, copies config)
./scripts/setup-local.sh

# 3. Install and start Ollama (in a new terminal)
brew install ollama
ollama pull llama3.1
ollama serve

# 4. Start the backend (in a new terminal)
source venv/bin/activate
uvicorn src.main:app --reload --port 8000

# 5. Start the frontend (in a new terminal)
cd frontend
npm install
npm run dev

# 6. Open http://localhost:5173 in your browser
# Login: girish / Girish@123
```

If the setup script doesn't exist or you prefer manual setup, follow the detailed steps below.

---

## Detailed Installation Steps

### Step 1: Clone the Repository

```bash
# Clone via HTTPS
git clone https://github.com/GirishAh-Kore/excel-rag.git

# Or clone via SSH (if you have SSH keys configured)
git clone git@github.com:GirishAh-Kore/excel-rag.git

# Navigate to the project directory
cd excel-rag
```

### Step 2: Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt):
.\venv\Scripts\activate.bat
```

**Verify activation:** Your terminal prompt should now show `(venv)` at the beginning.

### Step 3: Install Python Dependencies

```bash
# Upgrade pip first
pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt

# Install BGE-M3 for local embeddings (recommended)
pip install FlagEmbedding
```

**Expected output:** You should see packages being downloaded and installed. This may take 2-5 minutes.

### Step 4: Install Ollama (Local LLM)

Ollama allows you to run LLMs locally without any API costs.

**macOS:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download from https://ollama.com/download

**Pull the Llama 3.1 model:**
```bash
# This downloads ~4.7GB (one-time download)
ollama pull llama3.1
```

**Verify installation:**
```bash
ollama list
# Should show: llama3.1:latest
```

### Step 5: Configure Environment

```bash
# Copy the local development configuration
cp .env.local .env
```

The `.env.local` file is pre-configured for fully local operation:
- BGE-M3 embeddings (runs in-process)
- ChromaDB vector store (runs in-process)
- Ollama LLM (runs as separate service)
- No API keys required
- No Google Drive required (upload files directly)

**Optional: Review the configuration**
```bash
cat .env
```

### Step 6: Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

**Expected output:** You should see npm downloading packages. This may take 1-2 minutes.

---

## Running the Application

You need to run **3 processes** in separate terminal windows:

### Terminal 1: Ollama (LLM Server)

```bash
ollama serve
```

**Expected output:**
```
Couldn't find '/Users/.../.ollama/id_ed25519'. Generating new private key.
Your new public key is: ...
2024/xx/xx xx:xx:xx llama.cpp: loading model from ...
```

**Keep this terminal open.** Ollama needs to be running for the LLM to work.

### Terminal 2: Backend API

```bash
# Navigate to project directory
cd ~/path/to/excel-rag

# Activate virtual environment
source venv/bin/activate

# Start the backend server
uvicorn src.main:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx]
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**First run note:** On the first query, BGE-M3 will download its model (~2GB). You'll see:
```
Downloading model BAAI/bge-m3...
```
This is a one-time download. Subsequent runs use the cached model.

### Terminal 3: Frontend

```bash
# Navigate to frontend directory
cd ~/path/to/excel-rag/frontend

# Start the development server
npm run dev
```

**Expected output:**
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.168.x.x:5173/
  ➜  press h + enter to show help
```

---

## Using the Application

### Step 1: Open the Application

Open your browser and navigate to: **http://localhost:5173**

### Step 2: Login

Use the default credentials:
- **Username:** `girish`
- **Password:** `Girish@123`

### Step 3: Upload an Excel File

1. Click on the **"Upload Excel Files"** section
2. Either:
   - **Drag and drop** an Excel file (.xlsx, .xls, .xlsm)
   - **Click** to browse and select a file
3. Wait for the upload and indexing to complete
   - You'll see a progress bar
   - Status will change to "Upload complete"

**Watch Terminal 2** for indexing progress:
```
INFO: Processing file: your_file.xlsx
INFO: Extracted 3 sheets
INFO: Generated embeddings for 150 chunks
INFO: Indexing complete
```

### Step 4: Ask Questions

1. Type your question in the chat input at the bottom
2. Press Enter or click Send
3. Wait for the response (may take 5-30 seconds depending on your hardware)

**Example questions:**
- "What is the total revenue?"
- "Show me the top 5 products by sales"
- "What are the column headers in Sheet1?"
- "Compare Q1 and Q2 expenses"

### Step 5: View Sources

Each answer includes source citations showing:
- File name
- Sheet name
- Relevant data excerpts

---

## Configuration Options

### Option A: Fully Local (Default - No API Costs)

This is the default configuration in `.env.local`. Everything runs locally:

```bash
# LLM
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
LLM_BASE_URL=http://localhost:11434

# Embeddings
EMBEDDING_PROVIDER=bge-m3
EMBEDDING_MODEL=BAAI/bge-m3

# Vector Store
VECTOR_STORE_PROVIDER=chromadb
```

**Pros:** Free, private, no internet required after setup
**Cons:** Requires more RAM, slower than cloud APIs

### Option B: Cloud APIs (OpenAI)

For better quality responses with cloud APIs:

```bash
# Edit .env file
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-openai-api-key
LLM_MODEL=gpt-4o

EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-your-openai-api-key
EMBEDDING_MODEL=text-embedding-3-small
```

**Pros:** Faster, higher quality responses
**Cons:** Costs money, requires internet, data sent to cloud

### Option C: Hybrid (Local Embeddings + Cloud LLM)

Best balance of cost and quality:

```bash
# Edit .env file
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-openai-api-key
LLM_MODEL=gpt-4o

EMBEDDING_PROVIDER=bge-m3
EMBEDDING_MODEL=BAAI/bge-m3
```

**Pros:** Lower cost than full cloud, good quality
**Cons:** Still requires OpenAI API key

---

## Troubleshooting

### Issue: "Connection refused" when starting backend

**Cause:** Ollama is not running

**Solution:**
```bash
# In a separate terminal
ollama serve
```

### Issue: "No module named 'FlagEmbedding'"

**Cause:** BGE-M3 dependency not installed

**Solution:**
```bash
source venv/bin/activate
pip install FlagEmbedding
```

### Issue: Backend starts but embeddings fail

**Cause:** First-time model download in progress

**Solution:** Wait for the model to download (~2GB). Check Terminal 2 for progress.

### Issue: "CUDA out of memory" or memory errors

**Cause:** Not enough RAM for the model

**Solution:**
```bash
# Edit .env to use CPU instead of GPU
EMBEDDING_DEVICE=cpu

# Or use a smaller embedding model
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Issue: Ollama model not found

**Cause:** Model not downloaded

**Solution:**
```bash
ollama pull llama3.1
ollama list  # Verify it's downloaded
```

### Issue: Frontend shows blank page

**Cause:** Frontend not built or wrong URL

**Solution:**
```bash
cd frontend
npm install
npm run dev
# Make sure you're accessing http://localhost:5173 (not 8000)
```

### Issue: Login fails

**Cause:** Wrong credentials or backend not running

**Solution:**
- Verify backend is running (Terminal 2)
- Use credentials: `girish` / `Girish@123`

### Issue: File upload fails

**Cause:** File too large or wrong format

**Solution:**
- Ensure file is .xlsx, .xls, or .xlsm
- Maximum file size: 100MB
- Check Terminal 2 for error details

### Issue: Slow responses

**Cause:** Local LLM processing time

**Solution:**
- First response is slower (model loading)
- Subsequent responses are faster
- Consider using OpenAI for faster responses
- Use a smaller Ollama model: `ollama pull mistral`

---

## Architecture Overview

### What Runs Where

| Component | Type | Description |
|-----------|------|-------------|
| **Ollama** | Separate Service | Runs the LLM (Llama 3.1). Must be started separately. |
| **Backend API** | Python Process | FastAPI server handling uploads, queries, and orchestration. |
| **Frontend** | Node Process | React app for the user interface. |
| **BGE-M3** | In-Process | Embedding model runs inside the Python backend. |
| **ChromaDB** | In-Process | Vector database runs inside the Python backend. |

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Browser                             │
│                    http://localhost:5173                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                       │
│                    Terminal 3: npm run dev                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend API (FastAPI)                         │
│                    Terminal 2: uvicorn                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   BGE-M3    │  │  ChromaDB   │  │   Excel Extraction      │  │
│  │ (Embeddings)│  │  (Vectors)  │  │   (openpyxl)            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Ollama (LLM Server)                           │
│                    Terminal 1: ollama serve                      │
│                    Model: llama3.1 (4.7GB)                       │
└─────────────────────────────────────────────────────────────────┘
```

### File Storage

| Path | Contents |
|------|----------|
| `./chroma_db/` | Vector embeddings (ChromaDB) |
| `./data/metadata.db` | File metadata (SQLite) |
| `./uploads/` | Uploaded Excel files |
| `./tokens/` | OAuth tokens (if using Google Drive) |

---

## Next Steps

After successful installation:

1. **Upload your Excel files** and test queries
2. **Explore the API** at http://localhost:8000/docs
3. **Customize configuration** in `.env` for your needs
4. **Read the architecture docs** in `SOLUTION_ARCHITECTURE.md`

For questions or issues, check the GitHub repository or contact the team.
