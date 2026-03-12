#!/bin/bash

# =============================================================================
# Excel RAG System - Local Setup Script
# =============================================================================
# This script sets up the development environment for local testing.
# Run from the project root directory: ./scripts/setup-local.sh
# =============================================================================

set -e  # Exit on error

echo "=============================================="
echo "Excel RAG System - Local Setup"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
else
    echo -e "${RED}✗ Python 3 not found. Please install Python 3.10+${NC}"
    exit 1
fi

# Check Node.js
echo "Checking Node.js..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v)
    echo -e "${GREEN}✓ Node.js $NODE_VERSION found${NC}"
else
    echo -e "${YELLOW}⚠ Node.js not found. Frontend will not work.${NC}"
    echo "  Install with: brew install node"
fi

# Create virtual environment if it doesn't exist
echo ""
echo "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Activate virtual environment
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip -q
echo -e "${GREEN}✓ pip upgraded${NC}"

# Install Python dependencies
echo ""
echo "Installing Python dependencies (this may take a few minutes)..."
pip install -r requirements.txt -q
echo -e "${GREEN}✓ Core dependencies installed${NC}"

# Install BGE-M3 for local embeddings
echo ""
echo "Installing BGE-M3 for local embeddings..."
pip install FlagEmbedding -q
echo -e "${GREEN}✓ BGE-M3 installed${NC}"

# Copy environment file
echo ""
echo "Setting up environment configuration..."
if [ ! -f ".env" ]; then
    cp .env.local .env
    echo -e "${GREEN}✓ Environment file created from .env.local${NC}"
else
    echo -e "${YELLOW}⚠ .env already exists, skipping copy${NC}"
fi

# Create necessary directories
echo ""
echo "Creating data directories..."
mkdir -p chroma_db data uploads tokens logs
echo -e "${GREEN}✓ Directories created${NC}"

# Install frontend dependencies
echo ""
echo "Installing frontend dependencies..."
if [ -d "frontend" ]; then
    cd frontend
    if command -v npm &> /dev/null; then
        npm install -q
        echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
    else
        echo -e "${YELLOW}⚠ npm not found, skipping frontend setup${NC}"
    fi
    cd ..
fi

# Check for Ollama
echo ""
echo "Checking for Ollama..."
if command -v ollama &> /dev/null; then
    echo -e "${GREEN}✓ Ollama found${NC}"
    
    # Check if llama3.1 model is downloaded
    if ollama list 2>/dev/null | grep -q "llama3.1"; then
        echo -e "${GREEN}✓ llama3.1 model found${NC}"
    else
        echo -e "${YELLOW}⚠ llama3.1 model not found${NC}"
        echo "  Run: ollama pull llama3.1"
    fi
else
    echo -e "${YELLOW}⚠ Ollama not found${NC}"
    echo "  Install with: brew install ollama"
    echo "  Then run: ollama pull llama3.1"
fi

# Summary
echo ""
echo "=============================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Start Ollama (Terminal 1):"
echo "   ollama serve"
echo ""
echo "2. Start Backend (Terminal 2):"
echo "   source venv/bin/activate"
echo "   uvicorn src.main:app --reload --port 8000"
echo ""
echo "3. Start Frontend (Terminal 3):"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "4. Open http://localhost:5173 in your browser"
echo "   Login: girish / Girish@123"
echo ""
echo "=============================================="
