# Vector Store Migration Guide

This guide explains how to migrate data between different vector store implementations (ChromaDB and OpenSearch) in the Google Drive Excel RAG system.

## Overview

The system supports pluggable vector store implementations through an abstraction layer. This allows you to:
- Start with ChromaDB for MVP/development
- Migrate to OpenSearch for production scalability
- Switch back if needed with full rollback support

## Prerequisites

Before migrating, ensure you have:

1. **Both vector stores configured** in your environment:
   ```bash
   # ChromaDB configuration
   CHROMA_PERSIST_DIR=./chroma_db
   
   # OpenSearch configuration
   OPENSEARCH_HOST=localhost
   OPENSEARCH_PORT=9200
   OPENSEARCH_USERNAME=admin
   OPENSEARCH_PASSWORD=your-password
   ```

2. **Required packages installed**:
   ```bash
   pip install chromadb opensearch-py
   ```

3. **Backup space available**: Ensure you have enough disk space for backup files (typically 2-3x the size of your vector data)

## Migration Process

### Step 1: Verify Current Setup

Check your current vector store configuration:

```bash
python src/config.py
```

This will show your current configuration and validate all settings.

### Step 2: Prepare Target Vector Store

If migrating to OpenSearch, ensure it's running and accessible:

```bash
# Test OpenSearch connection
curl -u admin:your-password https://localhost:9200
```

### Step 3: Run Migration

#### ChromaDB to OpenSearch

```bash
python scripts/migrate_vector_store.py \
  --source chromadb \
  --target opensearch
```

#### OpenSearch to ChromaDB

```bash
python scripts/migrate_vector_store.py \
  --source opensearch \
  --target chromadb
```

### Step 4: Review Migration Report

The script will output a detailed report:

```json
{
  "start_time": "2024-01-15T10:30:00",
  "end_time": "2024-01-15T10:35:00",
  "elapsed_seconds": 300.5,
  "total_documents": 15000,
  "total_successful": 15000,
  "total_failed": 0,
  "backup_path": "./migration_backups/migration_backup_20240115_103000.json",
  "validation_passed": true,
  "collections": {
    "excel_sheets": {
      "exported": 10000,
      "successful": 10000,
      "failed": 0,
      "validation_passed": true
    },
    "excel_pivots": {
      "exported": 3000,
      "successful": 3000,
      "failed": 0,
      "validation_passed": true
    },
    "excel_charts": {
      "exported": 2000,
      "successful": 2000,
      "failed": 0,
      "validation_passed": true
    }
  }
}
```

### Step 5: Update Configuration

After successful migration, update your `.env` file:

```bash
# Change from chromadb to opensearch
VECTOR_STORE_PROVIDER=opensearch
```

### Step 6: Restart Application

Restart your application to use the new vector store:

```bash
# If using API
python src/main.py

# If using CLI
python src/cli.py query ask "test query"
```

### Step 7: Verify Application

Test that queries work correctly with the new vector store:

```bash
# Test a simple query
python src/cli.py query ask "What is the total revenue?"

# Check indexing status
python src/cli.py index status
```

## Advanced Options

### Migrate Specific Collections

To migrate only specific collections:

```bash
python scripts/migrate_vector_store.py \
  --source chromadb \
  --target opensearch \
  --collections excel_sheets excel_pivots
```

### Adjust Batch Size

For large datasets, adjust the batch size:

```bash
python scripts/migrate_vector_store.py \
  --source chromadb \
  --target opensearch \
  --batch-size 500
```

### Skip Backup

To skip backup creation (not recommended):

```bash
python scripts/migrate_vector_store.py \
  --source chromadb \
  --target opensearch \
  --no-backup
```

## Rollback Process

If migration fails or you need to revert:

### Automatic Rollback

Use the most recent backup:

```bash
python scripts/migrate_vector_store.py \
  --source opensearch \
  --target chromadb \
  --rollback
```

### Rollback to Specific Backup

First, list available backups:

```bash
python scripts/migrate_vector_store.py --list-backups
```

Then rollback to a specific backup:

```bash
python scripts/migrate_vector_store.py \
  --source opensearch \
  --target chromadb \
  --rollback \
  --backup-path ./migration_backups/migration_backup_20240115_103000.json
```

## Validation

The migration script performs automatic validation:

1. **Count Verification**: Ensures the number of documents matches between source and target
2. **Sample Verification**: Checks that data integrity is maintained
3. **Collection Existence**: Verifies all collections were created successfully

If validation fails, the script will:
- Report which collections failed
- Provide rollback instructions
- Keep the backup for manual recovery

## Troubleshooting

### Migration Fails with Connection Error

**Problem**: Cannot connect to target vector store

**Solution**:
```bash
# Check OpenSearch is running
curl -u admin:password https://localhost:9200

# Check ChromaDB directory exists and is writable
ls -la ./chroma_db
```

### Validation Fails with Count Mismatch

**Problem**: Document counts don't match after migration

**Solution**:
1. Check the migration report for specific collection issues
2. Verify network stability during migration
3. Try migrating with smaller batch size
4. Rollback and retry migration

### Out of Memory During Migration

**Problem**: Script crashes with memory error

**Solution**:
```bash
# Reduce batch size
python scripts/migrate_vector_store.py \
  --source chromadb \
  --target opensearch \
  --batch-size 50

# Or migrate collections one at a time
python scripts/migrate_vector_store.py \
  --source chromadb \
  --target opensearch \
  --collections excel_sheets
```

### Backup File Too Large

**Problem**: Backup file exceeds available disk space

**Solution**:
1. Free up disk space before migration
2. Use `--no-backup` flag (not recommended)
3. Migrate collections individually
4. Compress old backups: `gzip migration_backups/*.json`

## Best Practices

### Before Migration

1. **Stop all indexing operations**: Ensure no new data is being added during migration
2. **Backup your data**: Even though the script creates backups, maintain your own backups
3. **Test in development**: Run migration on a development environment first
4. **Check disk space**: Ensure sufficient space for backups and target store
5. **Document current state**: Note current document counts and collection sizes

### During Migration

1. **Monitor progress**: Watch the logs for any errors or warnings
2. **Don't interrupt**: Let the migration complete fully
3. **Check system resources**: Monitor CPU, memory, and network usage
4. **Keep backup safe**: Don't delete backup files until migration is verified

### After Migration

1. **Verify thoroughly**: Test multiple queries before switching production traffic
2. **Monitor performance**: Compare query performance between old and new stores
3. **Keep backups**: Retain backups for at least 7 days
4. **Update documentation**: Document the migration date and any issues encountered
5. **Clean up old data**: After verification, you can remove the old vector store data

## Performance Considerations

### ChromaDB to OpenSearch

- **Pros**: Better scalability, distributed search, production-ready
- **Cons**: Requires infrastructure setup, more complex configuration
- **Migration time**: ~5-10 minutes per 10,000 documents

### OpenSearch to ChromaDB

- **Pros**: Simpler setup, good for development, no infrastructure needed
- **Cons**: Limited scalability, single-node only
- **Migration time**: ~3-5 minutes per 10,000 documents

## Backup Management

### Backup Location

Backups are stored in `./migration_backups/` by default.

### Backup Format

Backups are JSON files containing:
- Document IDs
- Embedding vectors
- Original documents
- Metadata

### Backup Retention

Recommended retention policy:
- Keep last 3 backups: Always
- Keep weekly backups: 4 weeks
- Keep monthly backups: 3 months

### Manual Backup Cleanup

```bash
# Remove backups older than 30 days
find ./migration_backups -name "*.json" -mtime +30 -delete

# Compress old backups
gzip ./migration_backups/*.json
```

## Migration Checklist

Use this checklist for production migrations:

- [ ] Backup current data manually
- [ ] Stop all indexing operations
- [ ] Verify target vector store is accessible
- [ ] Check available disk space
- [ ] Run migration in maintenance window
- [ ] Review migration report
- [ ] Verify document counts
- [ ] Test sample queries
- [ ] Update configuration
- [ ] Restart application
- [ ] Monitor for errors
- [ ] Verify query performance
- [ ] Document migration completion
- [ ] Schedule backup cleanup

## Support

If you encounter issues during migration:

1. Check the migration logs in the console output
2. Review the backup files to ensure data was captured
3. Verify both vector stores are accessible
4. Check system resources (memory, disk space)
5. Try migrating with smaller batch sizes
6. Consult the troubleshooting section above

For persistent issues, check:
- Vector store documentation (ChromaDB, OpenSearch)
- Application logs in `./logs/`
- System logs for resource constraints

## Example Migration Scenarios

### Scenario 1: Development to Production

Moving from local ChromaDB to production OpenSearch:

```bash
# 1. Verify current setup
python src/config.py

# 2. Run migration
python scripts/migrate_vector_store.py \
  --source chromadb \
  --target opensearch

# 3. Update .env
echo "VECTOR_STORE_PROVIDER=opensearch" >> .env

# 4. Restart and verify
python src/main.py
```

### Scenario 2: Production Rollback

Rolling back from OpenSearch to ChromaDB:

```bash
# 1. Stop application
pkill -f "python src/main.py"

# 2. Rollback migration
python scripts/migrate_vector_store.py \
  --source opensearch \
  --target chromadb \
  --rollback

# 3. Update .env
echo "VECTOR_STORE_PROVIDER=chromadb" >> .env

# 4. Restart
python src/main.py
```

### Scenario 3: Partial Migration

Migrating only sheet data:

```bash
python scripts/migrate_vector_store.py \
  --source chromadb \
  --target opensearch \
  --collections excel_sheets
```

## Conclusion

The migration script provides a safe and reliable way to switch between vector store implementations. Always test migrations in a development environment first, maintain backups, and follow the best practices outlined in this guide.

For questions or issues, refer to the main README.md or consult the application documentation.
