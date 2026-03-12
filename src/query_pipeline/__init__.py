"""
Query Pipeline Module

This module implements the smart Excel query pipeline for file selection,
sheet selection, query classification, and answer generation.

Components:
- QueryPipelineOrchestrator: Central orchestrator coordinating the full pipeline.
- FileSelector: Ranks and selects files based on semantic similarity,
  metadata matching, and user preferences.
- SheetSelector: Ranks and selects sheets within files.
- QueryClassifier: Classifies queries into types (aggregation, lookup, etc.).
- QueryProcessorRegistry: Registry for query processors.
- BaseQueryProcessor: Abstract base class for query processors.
- AggregationProcessor: Processes aggregation queries.
- LookupProcessor: Processes lookup queries.
- SummarizationProcessor: Processes summarization queries.
- ComparisonProcessor: Processes comparison queries.
- AnswerGenerator: Generates answers with citations and confidence.

Supports Requirements 4.x, 5.x, 6.x, 7.x, 8.x, 9.x, 10.x, 11.x, 12.x, 14.x.
"""

from src.query_pipeline.file_selector import (
    FileSelector,
    FileSelectorConfig,
    FileSelectionResult,
    FileRankingExplanation,
    EmbeddingServiceProtocol,
    PreferenceStoreProtocol,
    FileMetadataProtocol,
)
from src.query_pipeline.sheet_selector import (
    SheetSelector,
    SheetSelectorConfig,
    SheetSelectionResult,
    SheetRankingExplanation,
    CombinationStrategy,
)
from src.query_pipeline.classifier import (
    QueryClassifier,
    ClassifierConfig,
    LLMServiceProtocol,
)
from src.query_pipeline.processor_registry import (
    QueryProcessorRegistry,
    register,
)
from src.query_pipeline.processors import (
    BaseQueryProcessor,
    ProcessedResult,
    RetrievedData,
    ProcessorConfig,
    AggregationProcessor,
    LookupProcessor,
    SummarizationProcessor,
    ComparisonProcessor,
)
from src.query_pipeline.answer_generator import (
    AnswerGenerator,
    AnswerGeneratorConfig,
    GeneratedAnswer,
)
from src.query_pipeline.orchestrator import (
    QueryPipelineOrchestrator,
    QueryPipelineConfig,
    SessionContext,
    DataRetrieverProtocol,
    SessionStoreProtocol,
)
from src.query_pipeline.cost_estimator import (
    QueryCostEstimator,
    CostEstimate,
    CostWeights,
    CostLimits,
    CostLevel,
    QueryCostBreakdown,
    QueryCostStatistics,
    CostAwareQueryError,
    create_cost_estimator,
)

__all__ = [
    # Orchestrator
    "QueryPipelineOrchestrator",
    "QueryPipelineConfig",
    "SessionContext",
    "DataRetrieverProtocol",
    "SessionStoreProtocol",
    # File Selector
    "FileSelector",
    "FileSelectorConfig",
    "FileSelectionResult",
    "FileRankingExplanation",
    "EmbeddingServiceProtocol",
    "PreferenceStoreProtocol",
    "FileMetadataProtocol",
    # Sheet Selector
    "SheetSelector",
    "SheetSelectorConfig",
    "SheetSelectionResult",
    "SheetRankingExplanation",
    "CombinationStrategy",
    # Query Classifier
    "QueryClassifier",
    "ClassifierConfig",
    "LLMServiceProtocol",
    # Processor Registry
    "QueryProcessorRegistry",
    "register",
    # Processors
    "BaseQueryProcessor",
    "ProcessedResult",
    "RetrievedData",
    "ProcessorConfig",
    "AggregationProcessor",
    "LookupProcessor",
    "SummarizationProcessor",
    "ComparisonProcessor",
    # Answer Generator
    "AnswerGenerator",
    "AnswerGeneratorConfig",
    "GeneratedAnswer",
    # Cost Estimator
    "QueryCostEstimator",
    "CostEstimate",
    "CostWeights",
    "CostLimits",
    "CostLevel",
    "QueryCostBreakdown",
    "QueryCostStatistics",
    "CostAwareQueryError",
    "create_cost_estimator",
]
