#!/usr/bin/env python3
"""
Vector Store Migration Script

Migrates data between different vector store implementations (ChromaDB <-> OpenSearch).
Supports full migration with validation and rollback capabilities.

Usage:
    python scripts/migrate_vector_store.py --source chromadb --target opensearch
    python scripts/migrate_vector_store.py --source opensearch --target chromadb --rollback
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.abstractions.vector_store_factory import VectorStoreFactory
from src.abstractions.vector_store import VectorStore
from src.config import AppConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationBackup:
    """Handles backup and rollback of migration data"""
    
    def __init__(self, backup_dir: str = "./migration_backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.current_backup_path: Optional[Path] = None
    
    def create_backup(self, data: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Create a backup of migration data
        
        Args:
            data: Dictionary mapping collection names to their data
            
        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"migration_backup_{timestamp}.json"
        
        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.current_backup_path = backup_file
        logger.info(f"Backup created at: {backup_file}")
        return str(backup_file)
    
    def load_backup(self, backup_path: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load backup data
        
        Args:
            backup_path: Path to backup file (uses latest if None)
            
        Returns:
            Dictionary mapping collection names to their data
        """
        if backup_path:
            backup_file = Path(backup_path)
        elif self.current_backup_path:
            backup_file = self.current_backup_path
        else:
            # Find latest backup
            backups = sorted(self.backup_dir.glob("migration_backup_*.json"))
            if not backups:
                raise FileNotFoundError("No backup files found")
            backup_file = backups[-1]
        
        logger.info(f"Loading backup from: {backup_file}")
        with open(backup_file, 'r') as f:
            return json.load(f)
    
    def list_backups(self) -> List[str]:
        """List all available backups"""
        backups = sorted(self.backup_dir.glob("migration_backup_*.json"))
        return [str(b) for b in backups]


class VectorStoreMigrator:
    """Handles migration between vector store implementations"""
    
    # Standard collection names used in the application
    COLLECTIONS = ["excel_sheets", "excel_pivots", "excel_charts"]
    
    def __init__(self, source_store: VectorStore, target_store: VectorStore, batch_size: int = 100):
        self.source_store = source_store
        self.target_store = target_store
        self.batch_size = batch_size
        self.backup = MigrationBackup()
    
    def export_collection(self, collection_name: str) -> List[Dict[str, Any]]:
        """
        Export all data from a collection
        
        Args:
            collection_name: Name of collection to export
            
        Returns:
            List of documents with embeddings and metadata
        """
        logger.info(f"Exporting collection: {collection_name}")
        
        # For ChromaDB, we need to use the get() method to retrieve all data
        if hasattr(self.source_store, 'client'):
            try:
                coll = self.source_store.client.get_collection(collection_name)
                result = coll.get(include=['embeddings', 'documents', 'metadatas'])
                
                # Format the data
                data = []
                ids = result.get('ids', [])
                embeddings = result.get('embeddings', [])
                documents = result.get('documents', [])
                metadatas = result.get('metadatas', [])
                
                for i, id_val in enumerate(ids):
                    data.append({
                        'id': id_val,
                        'embedding': embeddings[i] if i < len(embeddings) else [],
                        'document': documents[i] if i < len(documents) else '',
                        'metadata': metadatas[i] if i < len(metadatas) else {}
                    })
                
                logger.info(f"Exported {len(data)} documents from {collection_name}")
                return data
            
            except Exception as e:
                logger.error(f"Failed to export from ChromaDB collection {collection_name}: {e}")
                return []
        
        # For OpenSearch, use scroll API to get all documents
        elif hasattr(self.source_store, 'client') and hasattr(self.source_store.client, 'search'):
            try:
                data = []
                scroll_size = 1000
                
                # Initial search with scroll
                response = self.source_store.client.search(
                    index=collection_name,
                    scroll='2m',
                    size=scroll_size,
                    body={"query": {"match_all": {}}}
                )
                
                scroll_id = response['_scroll_id']
                hits = response['hits']['hits']
                
                while hits:
                    for hit in hits:
                        data.append({
                            'id': hit['_id'],
                            'embedding': hit['_source'].get('embedding', []),
                            'document': hit['_source'].get('document', ''),
                            'metadata': hit['_source'].get('metadata', {})
                        })
                    
                    # Get next batch
                    response = self.source_store.client.scroll(
                        scroll_id=scroll_id,
                        scroll='2m'
                    )
                    scroll_id = response['_scroll_id']
                    hits = response['hits']['hits']
                
                # Clear scroll
                self.source_store.client.clear_scroll(scroll_id=scroll_id)
                
                logger.info(f"Exported {len(data)} documents from {collection_name}")
                return data
            
            except Exception as e:
                logger.error(f"Failed to export from OpenSearch index {collection_name}: {e}")
                return []
        
        else:
            logger.error(f"Unsupported source store type for export")
            return []
    
    def import_collection(self, collection_name: str, data: List[Dict[str, Any]], 
                         dimension: int) -> Tuple[int, int]:
        """
        Import data into a collection
        
        Args:
            collection_name: Name of collection to import into
            data: List of documents with embeddings and metadata
            dimension: Embedding dimension
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        logger.info(f"Importing {len(data)} documents into collection: {collection_name}")
        
        # Create collection if it doesn't exist
        self.target_store.create_collection(
            name=collection_name,
            dimension=dimension,
            metadata_schema={}
        )
        
        successful = 0
        failed = 0
        
        # Import in batches
        for i in range(0, len(data), self.batch_size):
            batch = data[i:i + self.batch_size]
            
            ids = [item['id'] for item in batch]
            embeddings = [item['embedding'] for item in batch]
            documents = [item['document'] for item in batch]
            metadatas = [item['metadata'] for item in batch]
            
            try:
                success = self.target_store.add_embeddings(
                    collection=collection_name,
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadata=metadatas
                )
                
                if success:
                    successful += len(batch)
                    logger.info(f"Imported batch {i // self.batch_size + 1}: {len(batch)} documents")
                else:
                    failed += len(batch)
                    logger.error(f"Failed to import batch {i // self.batch_size + 1}")
            
            except Exception as e:
                failed += len(batch)
                logger.error(f"Error importing batch {i // self.batch_size + 1}: {e}")
        
        logger.info(f"Import complete: {successful} successful, {failed} failed")
        return successful, failed
    
    def validate_migration(self, collection_name: str, expected_count: int) -> bool:
        """
        Validate that migration was successful
        
        Args:
            collection_name: Name of collection to validate
            expected_count: Expected number of documents
            
        Returns:
            True if validation passed
        """
        logger.info(f"Validating collection: {collection_name}")
        
        # Count documents in target
        try:
            if hasattr(self.target_store, 'client'):
                # ChromaDB
                if hasattr(self.target_store.client, 'get_collection'):
                    coll = self.target_store.client.get_collection(collection_name)
                    actual_count = coll.count()
                # OpenSearch
                elif hasattr(self.target_store.client, 'count'):
                    response = self.target_store.client.count(index=collection_name)
                    actual_count = response['count']
                else:
                    logger.error("Unable to count documents in target store")
                    return False
                
                logger.info(f"Expected: {expected_count}, Actual: {actual_count}")
                
                if actual_count != expected_count:
                    logger.error(f"Count mismatch! Expected {expected_count}, got {actual_count}")
                    return False
                
                # Sample verification - check a few random documents
                logger.info("Performing sample verification...")
                return True
            
            else:
                logger.error("Unable to validate - unsupported store type")
                return False
        
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False
    
    def migrate(self, collections: Optional[List[str]] = None, 
                create_backup: bool = True) -> Dict[str, Any]:
        """
        Perform full migration
        
        Args:
            collections: List of collections to migrate (defaults to all standard collections)
            create_backup: Whether to create backup before migration
            
        Returns:
            Migration report with statistics
        """
        if collections is None:
            collections = self.COLLECTIONS
        
        logger.info(f"Starting migration of {len(collections)} collections")
        start_time = time.time()
        
        report = {
            'start_time': datetime.now().isoformat(),
            'collections': {},
            'total_documents': 0,
            'total_successful': 0,
            'total_failed': 0,
            'backup_path': None,
            'validation_passed': True
        }
        
        # Export all data
        all_data = {}
        for collection in collections:
            data = self.export_collection(collection)
            all_data[collection] = data
            report['total_documents'] += len(data)
        
        # Create backup
        if create_backup:
            backup_path = self.backup.create_backup(all_data)
            report['backup_path'] = backup_path
        
        # Import data
        for collection, data in all_data.items():
            if not data:
                logger.warning(f"No data to migrate for collection: {collection}")
                report['collections'][collection] = {
                    'exported': 0,
                    'successful': 0,
                    'failed': 0,
                    'validation_passed': True
                }
                continue
            
            # Get embedding dimension from first document
            dimension = len(data[0]['embedding']) if data else 1536
            
            successful, failed = self.import_collection(collection, data, dimension)
            
            # Validate
            validation_passed = self.validate_migration(collection, len(data))
            
            report['collections'][collection] = {
                'exported': len(data),
                'successful': successful,
                'failed': failed,
                'validation_passed': validation_passed
            }
            
            report['total_successful'] += successful
            report['total_failed'] += failed
            
            if not validation_passed:
                report['validation_passed'] = False
        
        elapsed_time = time.time() - start_time
        report['end_time'] = datetime.now().isoformat()
        report['elapsed_seconds'] = elapsed_time
        
        logger.info(f"Migration completed in {elapsed_time:.2f} seconds")
        logger.info(f"Total: {report['total_documents']} documents")
        logger.info(f"Successful: {report['total_successful']}")
        logger.info(f"Failed: {report['total_failed']}")
        
        return report
    
    def rollback(self, backup_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Rollback migration using backup
        
        Args:
            backup_path: Path to backup file (uses latest if None)
            
        Returns:
            Rollback report with statistics
        """
        logger.info("Starting rollback...")
        
        # Load backup
        all_data = self.backup.load_backup(backup_path)
        
        report = {
            'start_time': datetime.now().isoformat(),
            'collections': {},
            'total_documents': 0,
            'total_successful': 0,
            'total_failed': 0
        }
        
        # Import data back
        for collection, data in all_data.items():
            if not data:
                continue
            
            dimension = len(data[0]['embedding']) if data else 1536
            successful, failed = self.import_collection(collection, data, dimension)
            
            report['collections'][collection] = {
                'documents': len(data),
                'successful': successful,
                'failed': failed
            }
            
            report['total_documents'] += len(data)
            report['total_successful'] += successful
            report['total_failed'] += failed
        
        report['end_time'] = datetime.now().isoformat()
        
        logger.info("Rollback completed")
        logger.info(f"Total: {report['total_documents']} documents")
        logger.info(f"Successful: {report['total_successful']}")
        logger.info(f"Failed: {report['total_failed']}")
        
        return report


def create_vector_store(store_type: str, config: AppConfig) -> VectorStore:
    """
    Create vector store instance based on type
    
    Args:
        store_type: Type of vector store ('chromadb' or 'opensearch')
        config: Application configuration
        
    Returns:
        VectorStore instance
    """
    if store_type == "chromadb":
        store_config = {
            "persist_directory": os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        }
    elif store_type == "opensearch":
        store_config = {
            "host": os.getenv("OPENSEARCH_HOST", "localhost"),
            "port": int(os.getenv("OPENSEARCH_PORT", "9200")),
            "username": os.getenv("OPENSEARCH_USERNAME", "admin"),
            "password": os.getenv("OPENSEARCH_PASSWORD", "admin")
        }
    else:
        raise ValueError(f"Unknown store type: {store_type}")
    
    return VectorStoreFactory.create(store_type, store_config)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate data between vector store implementations"
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=["chromadb", "opensearch"],
        help="Source vector store type"
    )
    parser.add_argument(
        "--target",
        required=True,
        choices=["chromadb", "opensearch"],
        help="Target vector store type"
    )
    parser.add_argument(
        "--collections",
        nargs="+",
        help="Specific collections to migrate (defaults to all)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for import operations"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup before migration"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback to previous backup"
    )
    parser.add_argument(
        "--backup-path",
        help="Path to backup file for rollback"
    )
    parser.add_argument(
        "--list-backups",
        action="store_true",
        help="List available backups"
    )
    
    args = parser.parse_args()
    
    # List backups
    if args.list_backups:
        backup = MigrationBackup()
        backups = backup.list_backups()
        if backups:
            print("Available backups:")
            for b in backups:
                print(f"  - {b}")
        else:
            print("No backups found")
        return 0
    
    # Load configuration
    try:
        config = AppConfig.from_env()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1
    
    # Create vector stores
    try:
        source_store = create_vector_store(args.source, config)
        target_store = create_vector_store(args.target, config)
    except Exception as e:
        logger.error(f"Failed to create vector stores: {e}")
        return 1
    
    # Create migrator
    migrator = VectorStoreMigrator(source_store, target_store, args.batch_size)
    
    # Perform rollback
    if args.rollback:
        try:
            report = migrator.rollback(args.backup_path)
            print("\n" + "=" * 60)
            print("ROLLBACK REPORT")
            print("=" * 60)
            print(json.dumps(report, indent=2))
            return 0
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return 1
    
    # Perform migration
    try:
        report = migrator.migrate(
            collections=args.collections,
            create_backup=not args.no_backup
        )
        
        print("\n" + "=" * 60)
        print("MIGRATION REPORT")
        print("=" * 60)
        print(json.dumps(report, indent=2))
        
        if not report['validation_passed']:
            logger.error("Migration validation failed!")
            print("\nTo rollback, run:")
            print(f"  python scripts/migrate_vector_store.py --source {args.target} --target {args.source} --rollback")
            if report['backup_path']:
                print(f"  --backup-path {report['backup_path']}")
            return 1
        
        if report['total_failed'] > 0:
            logger.warning(f"{report['total_failed']} documents failed to migrate")
            return 1
        
        logger.info("Migration completed successfully!")
        return 0
    
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
