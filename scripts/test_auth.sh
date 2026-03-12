#!/bin/bash
# Quick authentication testing script

echo "=================================="
echo "Authentication Layer Test Script"
echo "=================================="
echo ""

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Virtual environment not activated"
    echo "   Run: source venv/bin/activate"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found"
    echo "   Copy .env.example to .env and configure it"
    exit 1
fi

echo "1. Running unit tests..."
python -m pytest tests/test_authentication.py -v
TEST_RESULT=$?

if [ $TEST_RESULT -eq 0 ]; then
    echo ""
    echo "✓ All tests passed!"
else
    echo ""
    echo "✗ Some tests failed"
    exit 1
fi

echo ""
echo "2. Checking configuration..."
python -c "from src.config import AppConfig; config = AppConfig.from_env(); print('✓ Configuration loaded'); print(f'  Client ID: {config.google_drive.client_id[:20] if config.google_drive.client_id else \"NOT SET\"}...'); print(f'  Token Path: {config.google_drive.token_storage_path}')"

echo ""
echo "3. Testing imports..."
python -c "from src.auth import AuthenticationService, AuthenticationStatus, OAuthFlow, TokenStorage, TokenRefreshManager; print('✓ All imports successful')"

echo ""
echo "=================================="
echo "Authentication layer is ready!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. Configure Google OAuth credentials in .env"
echo "  2. Generate encryption key: python examples/auth_usage.py genkey"
echo "  3. Test authentication: python examples/auth_usage.py auth"
echo ""
