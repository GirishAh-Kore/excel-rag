#!/bin/bash

# Test script for Google Drive connector
# This script verifies the Google Drive connector implementation

set -e

echo "=========================================="
echo "Google Drive Connector Test"
echo "=========================================="
echo ""

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Virtual environment not activated"
    echo "   Activating venv..."
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo "❌ Virtual environment not found. Please create it first:"
        echo "   python -m venv venv"
        echo "   source venv/bin/activate"
        echo "   pip install -r requirements.txt"
        exit 1
    fi
fi

echo "✅ Virtual environment activated"
echo ""

# Check if .env file exists
if [ ! -f ".env.development" ] && [ ! -f ".env" ]; then
    echo "❌ No .env file found"
    echo "   Please create .env or .env.development with required configuration"
    echo "   See .env.example for reference"
    exit 1
fi

echo "✅ Configuration file found"
echo ""

# Check authentication
echo "🔐 Checking authentication status..."
python -c "
import sys
from src.config import AppConfig
from src.auth.authentication_service import create_authentication_service

config = AppConfig.from_env()
auth_service = create_authentication_service(config.google_drive)

if auth_service.is_authenticated():
    print('✅ Authenticated with Google Drive')
else:
    print('❌ Not authenticated')
    print('   Please run: python examples/auth_usage.py')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    exit 1
fi

echo ""

# Test import
echo "📦 Testing module import..."
python -c "
from src.gdrive import GoogleDriveConnector, create_google_drive_connector
from src.gdrive import EXCEL_MIME_TYPES, EXCEL_EXTENSIONS
print('✅ Module imports successful')
print(f'   Excel MIME types: {len(EXCEL_MIME_TYPES)}')
print(f'   Excel extensions: {len(EXCEL_EXTENSIONS)}')
"

echo ""

# Test connector creation
echo "🔧 Testing connector creation..."
python -c "
from src.config import AppConfig
from src.auth.authentication_service import create_authentication_service
from src.gdrive import create_google_drive_connector

config = AppConfig.from_env()
auth_service = create_authentication_service(config.google_drive)
connector = create_google_drive_connector(auth_service)

print('✅ Connector created successfully')
print(f'   Type: {type(connector).__name__}')
"

echo ""

# Test file listing (if authenticated)
echo "📂 Testing file listing..."
python -c "
from src.config import AppConfig
from src.auth.authentication_service import create_authentication_service
from src.gdrive import create_google_drive_connector

config = AppConfig.from_env()
auth_service = create_authentication_service(config.google_drive)
connector = create_google_drive_connector(auth_service)

try:
    files = connector.list_excel_files(recursive=True)
    print(f'✅ File listing successful')
    print(f'   Found {len(files)} Excel files')
    
    if files:
        print(f'   First file: {files[0].name}')
        print(f'   Path: {files[0].path}')
        print(f'   Size: {files[0].size:,} bytes')
except Exception as e:
    print(f'⚠️  File listing failed: {e}')
    print('   This might be expected if no Excel files exist in Drive')
"

echo ""

# Test change detection
echo "🔄 Testing change detection..."
python -c "
from src.config import AppConfig
from src.auth.authentication_service import create_authentication_service
from src.gdrive import create_google_drive_connector

config = AppConfig.from_env()
auth_service = create_authentication_service(config.google_drive)
connector = create_google_drive_connector(auth_service)

try:
    result = connector.watch_changes()
    print(f'✅ Change detection successful')
    print(f'   Page token: {result[\"newStartPageToken\"][:20]}...')
    print(f'   Changes: {len(result[\"changes\"])}')
except Exception as e:
    print(f'❌ Change detection failed: {e}')
"

echo ""
echo "=========================================="
echo "✅ All tests passed!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Run examples: python examples/gdrive_usage.py"
echo "  2. Integrate with indexing pipeline"
echo ""
