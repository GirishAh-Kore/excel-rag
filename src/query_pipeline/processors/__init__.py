"""
Query Processors Package.

This package contains query processor implementations for different query types:
- BaseQueryProcessor: Abstract base class for all processors
- AggregationProcessor: Handles SUM, AVG, COUNT, MIN, MAX, MEDIAN queries
- LookupProcessor: Handles value lookup queries
- SummarizationProcessor: Handles data summarization queries
- ComparisonProcessor: Handles data comparison queries

All processors follow the registry pattern and can be retrieved via
QueryProcessorRegistry.get_processor().

Supports Requirements 7.1, 8.1, 9.1, 10.1.
"""

from src.query_pipeline.processors.base import (
    BaseQueryProcessor,
    ProcessedResult,
    RetrievedData,
    ProcessorConfig,
)

# Import processors to trigger registration via @register decorator
from src.query_pipeline.processors.aggregation import AggregationProcessor
from src.query_pipeline.processors.lookup import LookupProcessor
from src.query_pipeline.processors.summarization import SummarizationProcessor
from src.query_pipeline.processors.comparison import ComparisonProcessor

__all__ = [
    "BaseQueryProcessor",
    "ProcessedResult",
    "RetrievedData",
    "ProcessorConfig",
    "AggregationProcessor",
    "LookupProcessor",
    "SummarizationProcessor",
    "ComparisonProcessor",
]
