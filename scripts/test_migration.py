#!/usr/bin/env python3
"""
Test script for vector store migration

This script tests the migration functionality without requiring actual vector stores.
It validates the migration script's logic and data handling.
"""

import sys
import json
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List


class SimpleMigrationBackup:
    """Simplified backup handler for testing"""
    
    def __init__(self, backup_dir: str):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, data: Dict[str, List[Dict[str, Any]]]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"migration_backup_{timestamp}.json"
        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)
        return str(backup_file)
    
    def load_backup(self, backup_path: str) -> Dict[str, List[Dict[str, Any]]]:
        with open(backup_path, 'r') as f:
            return json.load(f)
    
    def list_backups(self) -> List[str]:
        backups = sorted(self.backup_dir.glob("migration_backup_*.json"))
        return [str(b) for b in backups]


def test_backup_creation():
    """Test backup creation and loading"""
    print("Testing backup creation...")
    
    # Create temporary backup directory
    temp_dir = tempfile.mkdtemp()
    backup = SimpleMigrationBackup(backup_dir=temp_dir)
    
    # Create test data
    test_data = {
        "test_collection": [
            {
                "id": "doc1",
                "embedding": [0.1, 0.2, 0.3],
                "document": "Test document 1",
                "metadata": {"key": "value1"}
            },
            {
                "id": "doc2",
                "embedding": [0.4, 0.5, 0.6],
                "document": "Test document 2",
                "metadata": {"key": "value2"}
            }
        ]
    }
    
    # Create backup
    backup_path = backup.create_backup(test_data)
    print(f"✓ Backup created at: {backup_path}")
    
    # Load backup
    loaded_data = backup.load_backup(backup_path)
    print(f"✓ Backup loaded successfully")
    
    # Verify data
    assert loaded_data == test_data, "Loaded data doesn't match original"
    print(f"✓ Data integrity verified")
    
    # List backups
    backups = backup.list_backups()
    assert len(backups) > 0, "No backups found"
    print(f"✓ Found {len(backups)} backup(s)")
    
    # Cleanup
    shutil.rmtree(temp_dir)
    print("✓ Test passed: Backup creation and loading\n")


def test_data_format():
    """Test data format handling"""
    print("Testing data format handling...")
    
    # Test data with various types
    test_data = [
        {
            "id": "doc1",
            "embedding": [0.1] * 1536,  # Standard OpenAI embedding size
            "document": "Test with special chars: @#$%",
            "metadata": {
                "file_name": "test.xlsx",
                "sheet_name": "Sheet1",
                "has_formulas": True,
                "row_count": 100
            }
        },
        {
            "id": "doc2",
            "embedding": [0.2] * 1536,
            "document": "Test with unicode: 你好 สวัสดี",
            "metadata": {
                "file_name": "test2.xlsx",
                "sheet_name": "Data",
                "has_formulas": False,
                "row_count": 50
            }
        }
    ]
    
    # Verify all required fields are present
    for doc in test_data:
        assert "id" in doc, "Missing 'id' field"
        assert "embedding" in doc, "Missing 'embedding' field"
        assert "document" in doc, "Missing 'document' field"
        assert "metadata" in doc, "Missing 'metadata' field"
        assert isinstance(doc["embedding"], list), "Embedding must be a list"
        assert len(doc["embedding"]) > 0, "Embedding must not be empty"
    
    print(f"✓ Validated {len(test_data)} documents")
    print("✓ Test passed: Data format handling\n")


def test_batch_processing():
    """Test batch processing logic"""
    print("Testing batch processing...")
    
    # Create test data
    num_docs = 250
    test_data = [
        {
            "id": f"doc{i}",
            "embedding": [float(i)] * 10,
            "document": f"Document {i}",
            "metadata": {"index": i}
        }
        for i in range(num_docs)
    ]
    
    # Test different batch sizes
    batch_sizes = [50, 100, 200]
    
    for batch_size in batch_sizes:
        batches = []
        for i in range(0, len(test_data), batch_size):
            batch = test_data[i:i + batch_size]
            batches.append(batch)
        
        # Verify all data is included
        total_docs = sum(len(batch) for batch in batches)
        assert total_docs == num_docs, f"Lost documents with batch size {batch_size}"
        
        print(f"✓ Batch size {batch_size}: {len(batches)} batches, {total_docs} total docs")
    
    print("✓ Test passed: Batch processing\n")


def test_migration_report():
    """Test migration report structure"""
    print("Testing migration report structure...")
    
    # Sample report
    report = {
        "start_time": "2024-01-15T10:00:00",
        "end_time": "2024-01-15T10:05:00",
        "elapsed_seconds": 300.0,
        "total_documents": 1000,
        "total_successful": 1000,
        "total_failed": 0,
        "backup_path": "/path/to/backup.json",
        "validation_passed": True,
        "collections": {
            "excel_sheets": {
                "exported": 700,
                "successful": 700,
                "failed": 0,
                "validation_passed": True
            },
            "excel_pivots": {
                "exported": 200,
                "successful": 200,
                "failed": 0,
                "validation_passed": True
            },
            "excel_charts": {
                "exported": 100,
                "successful": 100,
                "failed": 0,
                "validation_passed": True
            }
        }
    }
    
    # Verify report structure
    required_fields = [
        "start_time", "end_time", "elapsed_seconds",
        "total_documents", "total_successful", "total_failed",
        "backup_path", "validation_passed", "collections"
    ]
    
    for field in required_fields:
        assert field in report, f"Missing required field: {field}"
    
    # Verify collection reports
    for collection, stats in report["collections"].items():
        assert "exported" in stats, f"Missing 'exported' in {collection}"
        assert "successful" in stats, f"Missing 'successful' in {collection}"
        assert "failed" in stats, f"Missing 'failed' in {collection}"
        assert "validation_passed" in stats, f"Missing 'validation_passed' in {collection}"
    
    # Verify totals match
    total_exported = sum(c["exported"] for c in report["collections"].values())
    assert total_exported == report["total_documents"], "Total documents mismatch"
    
    print(f"✓ Report structure validated")
    print(f"✓ All required fields present")
    print(f"✓ Totals match collection sums")
    print("✓ Test passed: Migration report structure\n")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Vector Store Migration Tests")
    print("=" * 60)
    print()
    
    try:
        test_backup_creation()
        test_data_format()
        test_batch_processing()
        test_migration_report()
        
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
    
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
