#!/bin/bash
# Install language processing dependencies for Thai + English support

set -e  # Exit on error

echo "=========================================="
echo "Installing Language Processing Dependencies"
echo "=========================================="

# Check if running in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Not running in a virtual environment"
    echo "   Consider activating your venv first"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "1. Installing language detection libraries..."
pip install langdetect fasttext-wheel

echo ""
echo "2. Installing spaCy for English processing..."
pip install spacy

echo ""
echo "3. Downloading spaCy English model..."
python -m spacy download en_core_web_sm

echo ""
echo "4. Installing pythainlp for Thai processing..."
pip install pythainlp

echo ""
echo "5. Downloading pythainlp data..."
python -m pythainlp data install

echo ""
echo "6. Installing NLTK for additional text processing..."
pip install nltk

echo ""
echo "7. Downloading NLTK data..."
python -c "import nltk; nltk.download('punkt'); nltk.download('wordnet'); nltk.download('omw-1.4')"

echo ""
echo "8. Installing fuzzy matching library..."
pip install python-Levenshtein

echo ""
echo "=========================================="
echo "✅ All language dependencies installed!"
echo "=========================================="
echo ""
echo "Installed:"
echo "  ✓ langdetect - Language detection"
echo "  ✓ fasttext - Advanced language detection"
echo "  ✓ spaCy + en_core_web_sm - English NLP"
echo "  ✓ pythainlp - Thai NLP"
echo "  ✓ NLTK - Text processing utilities"
echo "  ✓ python-Levenshtein - Fuzzy matching"
echo ""
echo "You can now use multi-language features!"
