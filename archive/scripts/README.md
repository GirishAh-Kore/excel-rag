# Scripts Directory

This directory contains utility scripts for the Google Drive Excel RAG system.

## Available Scripts

### migrate_vector_store.py

Migrates data between different vector store implementations (ChromaDB ↔ OpenSearch).

**Features:**
- Full data export and import
- Automatic backup creation
- Data validation
- Rollback capability
- Batch processing for large datasets

**Usage:**

```bash
# Migrate from ChromaDB to OpenSearch
python scripts/migrate_vector_store.py --source chromadb --target opensearch

# Migrate from OpenSearch to ChromaDB
python scripts/migrate_vector_store.py --source opensearch --target chromadb

# Rollback to previous backup
python scripts/migrate_vector_store.py --source opensearch --target chromadb --rollback

# List available backups
python scripts/migrate_vector_store.py --list-backups

# Migrate specific collections only
python scripts/migrate_vector_store.py --source chromadb --target opensearch --collections excel_sheets

# Adjust batch size for large datasets
python scripts/migrate_vector_store.py --source chromadb --target opensearch --batch-size 500

# Skip backup creation (not recommended)
python scripts/migrate_vector_store.py --source chromadb --target opensearch --no-backup
```

**See also:** [docs/MIGRATION.md](../docs/MIGRATION.md) for detailed migration guide

### test_migration.py

Tests the migration script functionality without requiring actual vector stores.

**Usage:**

```bash
python scripts/test_migration.py
```

**Tests:**
- Backup creation and loading
- Data format validation
- Batch processing logic
- Migration report structure

### install_language_dependencies.sh

Installs language processing dependencies for multi-language support (English and Thai).

**Usage:**

```bash
bash scripts/install_language_dependencies.sh
```

**Installs:**
- spaCy English model
- pythainlp Thai language data
- NLTK corpora
- fasttext language detection model

### test_auth.sh

Tests Google Drive authentication setup.

**Usage:**

```bash
bash scripts/test_auth.sh
```

### test_gdrive.sh

Tests Google Drive connector functionality.

**Usage:**

```bash
bash scripts/test_gdrive.sh
```

## Environment Setup

All scripts require proper environment configuration. Ensure your `.env` file is set up correctly:

```bash
# Copy example configuration
cp .env.example .env

# Edit with your values
nano .env
```

## Common Issues

### ModuleNotFoundError

If you get import errors, ensure you're running scripts from the project root:

```bash
# From project root
python scripts/migrate_vector_store.py --help
```

### Permission Denied

Make scripts executable:

```bash
chmod +x scripts/*.py
chmod +x scripts/*.sh
```

### Connection Errors

Verify vector store connectivity:

```bash
# Test ChromaDB
ls -la ./chroma_db

# Test OpenSearch
curl -u admin:password https://localhost:9200
```

## Development

### Adding New Scripts

1. Create script in `scripts/` directory
2. Add shebang line: `#!/usr/bin/env python3` or `#!/bin/bash`
3. Make executable: `chmod +x scripts/your_script.py`
4. Document in this README
5. Add usage examples

### Testing Scripts

Create corresponding test scripts in `scripts/test_*.py` format.

## Support

For issues or questions:
- Check the main [README.md](../README.md)
- Review [docs/MIGRATION.md](../docs/MIGRATION.md) for migration-specific help
- Check application logs in `./logs/`
