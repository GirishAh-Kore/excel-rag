"""
Batch query processing module.

This module provides batch query processing capabilities for executing
multiple queries in parallel with progress tracking.

Key Components:
- BatchQueryProcessor: Processes arrays of queries with parallel execution
- BatchQueryStore: Persists batch status and results

Supports Requirements 24.1, 24.2, 24.3, 24.4, 24.5.
"""

from src.batch.processor import BatchQueryProcessor
from src.batch.store import BatchQueryStore

__all__ = ["BatchQueryProcessor", "BatchQueryStore"]
