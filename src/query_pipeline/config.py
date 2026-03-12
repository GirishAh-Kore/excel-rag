"""
Query Pipeline Configuration Module.

This module defines all configurable parameters for the Excel Query Pipeline
with sensible defaults and environment variable overrides.

Configuration Categories:
- File Selection: Thresholds and weights for file ranking
- Sheet Selection: Thresholds and weights for sheet ranking
- Query Classification: Confidence thresholds and LLM settings
- Query Processing: Timeouts, limits, and performance settings
- Caching: TTL and invalidation settings
- Traceability: Retention and export settings

Usage:
    from src.query_pipeline.config import get_query_pipeline_config
    
    config = get_query_pipeline_config()
    threshold = config.file_selection.auto_select_threshold

Environment Variables:
    All settings can be overridden via environment variables with the
    QUERY_PIPELINE_ prefix. See individual dataclass fields for variable names.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from src.exceptions import ConfigurationError


def _get_env_float(name: str, default: float) -> float:
    """Get float from environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        raise ConfigurationError(f"{name} must be a valid float, got: {value}")


def _get_env_int(name: str, default: int) -> int:
    """Get integer from environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise ConfigurationError(f"{name} must be a valid integer, got: {value}")


def _get_env_bool(name: str, default: bool) -> bool:
    """Get boolean from environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


@dataclass(frozen=True)
class FileSelectionConfig:
    """
    Configuration for file selection and ranking.
    
    Attributes:
        auto_select_threshold: Score above which files are auto-selected (0.0-1.0).
            Env: QUERY_PIPELINE_FILE_AUTO_SELECT_THRESHOLD
        clarification_threshold: Score below which clarification is requested (0.0-1.0).
            Env: QUERY_PIPELINE_FILE_CLARIFICATION_THRESHOLD
        low_confidence_threshold: Score below which results are marked low-confidence (0.0-1.0).
            Env: QUERY_PIPELINE_FILE_LOW_CONFIDENCE_THRESHOLD
        semantic_weight: Weight for semantic similarity in scoring (0.0-1.0).
            Env: QUERY_PIPELINE_FILE_SEMANTIC_WEIGHT
        metadata_weight: Weight for metadata matching in scoring (0.0-1.0).
            Env: QUERY_PIPELINE_FILE_METADATA_WEIGHT
        preference_weight: Weight for user preference history in scoring (0.0-1.0).
            Env: QUERY_PIPELINE_FILE_PREFERENCE_WEIGHT
        max_candidates: Maximum number of file candidates to consider.
            Env: QUERY_PIPELINE_FILE_MAX_CANDIDATES
        temporal_boost_factor: Boost factor for files matching temporal references.
            Env: QUERY_PIPELINE_FILE_TEMPORAL_BOOST
    """
    auto_select_threshold: float = 0.9
    clarification_threshold: float = 0.5
    low_confidence_threshold: float = 0.5
    semantic_weight: float = 0.5
    metadata_weight: float = 0.3
    preference_weight: float = 0.2
    max_candidates: int = 10
    temporal_boost_factor: float = 1.2
    
    @classmethod
    def from_env(cls) -> "FileSelectionConfig":
        """Load configuration from environment variables."""
        return cls(
            auto_select_threshold=_get_env_float(
                "QUERY_PIPELINE_FILE_AUTO_SELECT_THRESHOLD", 0.9
            ),
            clarification_threshold=_get_env_float(
                "QUERY_PIPELINE_FILE_CLARIFICATION_THRESHOLD", 0.5
            ),
            low_confidence_threshold=_get_env_float(
                "QUERY_PIPELINE_FILE_LOW_CONFIDENCE_THRESHOLD", 0.5
            ),
            semantic_weight=_get_env_float(
                "QUERY_PIPELINE_FILE_SEMANTIC_WEIGHT", 0.5
            ),
            metadata_weight=_get_env_float(
                "QUERY_PIPELINE_FILE_METADATA_WEIGHT", 0.3
            ),
            preference_weight=_get_env_float(
                "QUERY_PIPELINE_FILE_PREFERENCE_WEIGHT", 0.2
            ),
            max_candidates=_get_env_int(
                "QUERY_PIPELINE_FILE_MAX_CANDIDATES", 10
            ),
            temporal_boost_factor=_get_env_float(
                "QUERY_PIPELINE_FILE_TEMPORAL_BOOST", 1.2
            ),
        )
    
    def validate(self) -> list[str]:
        """Validate configuration values."""
        errors = []
        if not 0.0 <= self.auto_select_threshold <= 1.0:
            errors.append("auto_select_threshold must be between 0.0 and 1.0")
        if not 0.0 <= self.clarification_threshold <= 1.0:
            errors.append("clarification_threshold must be between 0.0 and 1.0")
        if not 0.0 <= self.low_confidence_threshold <= 1.0:
            errors.append("low_confidence_threshold must be between 0.0 and 1.0")
        if self.clarification_threshold >= self.auto_select_threshold:
            errors.append("clarification_threshold must be less than auto_select_threshold")
        weights_sum = self.semantic_weight + self.metadata_weight + self.preference_weight
        if abs(weights_sum - 1.0) > 0.01:
            errors.append(f"File selection weights must sum to 1.0, got {weights_sum}")
        if self.max_candidates < 1:
            errors.append("max_candidates must be at least 1")
        return errors


@dataclass(frozen=True)
class SheetSelectionConfig:
    """
    Configuration for sheet selection and ranking.
    
    Attributes:
        auto_select_threshold: Score above which sheets are auto-selected (0.0-1.0).
            Env: QUERY_PIPELINE_SHEET_AUTO_SELECT_THRESHOLD
        clarification_threshold: Score below which clarification is requested (0.0-1.0).
            Env: QUERY_PIPELINE_SHEET_CLARIFICATION_THRESHOLD
        name_weight: Weight for sheet name matching in scoring (0.0-1.0).
            Env: QUERY_PIPELINE_SHEET_NAME_WEIGHT
        header_weight: Weight for header matching in scoring (0.0-1.0).
            Env: QUERY_PIPELINE_SHEET_HEADER_WEIGHT
        data_type_weight: Weight for data type matching in scoring (0.0-1.0).
            Env: QUERY_PIPELINE_SHEET_DATA_TYPE_WEIGHT
        content_weight: Weight for content matching in scoring (0.0-1.0).
            Env: QUERY_PIPELINE_SHEET_CONTENT_WEIGHT
        max_sheets_per_query: Maximum sheets to combine in a single query.
            Env: QUERY_PIPELINE_SHEET_MAX_PER_QUERY
    """
    auto_select_threshold: float = 0.7
    clarification_threshold: float = 0.5
    name_weight: float = 0.3
    header_weight: float = 0.4
    data_type_weight: float = 0.2
    content_weight: float = 0.1
    max_sheets_per_query: int = 5
    
    @classmethod
    def from_env(cls) -> "SheetSelectionConfig":
        """Load configuration from environment variables."""
        return cls(
            auto_select_threshold=_get_env_float(
                "QUERY_PIPELINE_SHEET_AUTO_SELECT_THRESHOLD", 0.7
            ),
            clarification_threshold=_get_env_float(
                "QUERY_PIPELINE_SHEET_CLARIFICATION_THRESHOLD", 0.5
            ),
            name_weight=_get_env_float(
                "QUERY_PIPELINE_SHEET_NAME_WEIGHT", 0.3
            ),
            header_weight=_get_env_float(
                "QUERY_PIPELINE_SHEET_HEADER_WEIGHT", 0.4
            ),
            data_type_weight=_get_env_float(
                "QUERY_PIPELINE_SHEET_DATA_TYPE_WEIGHT", 0.2
            ),
            content_weight=_get_env_float(
                "QUERY_PIPELINE_SHEET_CONTENT_WEIGHT", 0.1
            ),
            max_sheets_per_query=_get_env_int(
                "QUERY_PIPELINE_SHEET_MAX_PER_QUERY", 5
            ),
        )
    
    def validate(self) -> list[str]:
        """Validate configuration values."""
        errors = []
        if not 0.0 <= self.auto_select_threshold <= 1.0:
            errors.append("auto_select_threshold must be between 0.0 and 1.0")
        if not 0.0 <= self.clarification_threshold <= 1.0:
            errors.append("clarification_threshold must be between 0.0 and 1.0")
        weights_sum = (
            self.name_weight + self.header_weight + 
            self.data_type_weight + self.content_weight
        )
        if abs(weights_sum - 1.0) > 0.01:
            errors.append(f"Sheet selection weights must sum to 1.0, got {weights_sum}")
        if self.max_sheets_per_query < 1:
            errors.append("max_sheets_per_query must be at least 1")
        return errors


@dataclass(frozen=True)
class ClassificationConfig:
    """
    Configuration for query classification.
    
    Attributes:
        confidence_threshold: Threshold below which LLM is used for classification.
            Env: QUERY_PIPELINE_CLASSIFICATION_CONFIDENCE_THRESHOLD
        alternative_threshold: Threshold below which alternative types are suggested.
            Env: QUERY_PIPELINE_CLASSIFICATION_ALTERNATIVE_THRESHOLD
        use_llm_for_ambiguous: Whether to use LLM for ambiguous classifications.
            Env: QUERY_PIPELINE_CLASSIFICATION_USE_LLM
        llm_timeout_seconds: Timeout for LLM classification requests.
            Env: QUERY_PIPELINE_CLASSIFICATION_LLM_TIMEOUT
    """
    confidence_threshold: float = 0.8
    alternative_threshold: float = 0.6
    use_llm_for_ambiguous: bool = True
    llm_timeout_seconds: int = 10
    
    @classmethod
    def from_env(cls) -> "ClassificationConfig":
        """Load configuration from environment variables."""
        return cls(
            confidence_threshold=_get_env_float(
                "QUERY_PIPELINE_CLASSIFICATION_CONFIDENCE_THRESHOLD", 0.8
            ),
            alternative_threshold=_get_env_float(
                "QUERY_PIPELINE_CLASSIFICATION_ALTERNATIVE_THRESHOLD", 0.6
            ),
            use_llm_for_ambiguous=_get_env_bool(
                "QUERY_PIPELINE_CLASSIFICATION_USE_LLM", True
            ),
            llm_timeout_seconds=_get_env_int(
                "QUERY_PIPELINE_CLASSIFICATION_LLM_TIMEOUT", 10
            ),
        )
    
    def validate(self) -> list[str]:
        """Validate configuration values."""
        errors = []
        if not 0.0 <= self.confidence_threshold <= 1.0:
            errors.append("confidence_threshold must be between 0.0 and 1.0")
        if not 0.0 <= self.alternative_threshold <= 1.0:
            errors.append("alternative_threshold must be between 0.0 and 1.0")
        if self.llm_timeout_seconds < 1:
            errors.append("llm_timeout_seconds must be at least 1")
        return errors


@dataclass(frozen=True)
class ProcessingConfig:
    """
    Configuration for query processing.
    
    Attributes:
        default_timeout_seconds: Default timeout for query processing.
            Env: QUERY_PIPELINE_PROCESSING_TIMEOUT
        max_chunks_per_query: Maximum chunks to retrieve per query.
            Env: QUERY_PIPELINE_PROCESSING_MAX_CHUNKS
        max_rows_for_aggregation: Maximum rows to process for aggregation queries.
            Env: QUERY_PIPELINE_PROCESSING_MAX_ROWS_AGGREGATION
        lookup_result_limit: Maximum results to return for lookup queries.
            Env: QUERY_PIPELINE_PROCESSING_LOOKUP_LIMIT
        summarization_sample_size: Sample size for large dataset summarization.
            Env: QUERY_PIPELINE_PROCESSING_SUMMARIZATION_SAMPLE
        summarization_max_words: Maximum words in summarization output.
            Env: QUERY_PIPELINE_PROCESSING_SUMMARIZATION_MAX_WORDS
        enable_streaming: Whether to enable streaming responses.
            Env: QUERY_PIPELINE_PROCESSING_ENABLE_STREAMING
    """
    default_timeout_seconds: int = 30
    max_chunks_per_query: int = 20
    max_rows_for_aggregation: int = 100000
    lookup_result_limit: int = 10
    summarization_sample_size: int = 1000
    summarization_max_words: int = 500
    enable_streaming: bool = True
    
    @classmethod
    def from_env(cls) -> "ProcessingConfig":
        """Load configuration from environment variables."""
        return cls(
            default_timeout_seconds=_get_env_int(
                "QUERY_PIPELINE_PROCESSING_TIMEOUT", 30
            ),
            max_chunks_per_query=_get_env_int(
                "QUERY_PIPELINE_PROCESSING_MAX_CHUNKS", 20
            ),
            max_rows_for_aggregation=_get_env_int(
                "QUERY_PIPELINE_PROCESSING_MAX_ROWS_AGGREGATION", 100000
            ),
            lookup_result_limit=_get_env_int(
                "QUERY_PIPELINE_PROCESSING_LOOKUP_LIMIT", 10
            ),
            summarization_sample_size=_get_env_int(
                "QUERY_PIPELINE_PROCESSING_SUMMARIZATION_SAMPLE", 1000
            ),
            summarization_max_words=_get_env_int(
                "QUERY_PIPELINE_PROCESSING_SUMMARIZATION_MAX_WORDS", 500
            ),
            enable_streaming=_get_env_bool(
                "QUERY_PIPELINE_PROCESSING_ENABLE_STREAMING", True
            ),
        )
    
    def validate(self) -> list[str]:
        """Validate configuration values."""
        errors = []
        if self.default_timeout_seconds < 1:
            errors.append("default_timeout_seconds must be at least 1")
        if self.max_chunks_per_query < 1:
            errors.append("max_chunks_per_query must be at least 1")
        if self.lookup_result_limit < 1:
            errors.append("lookup_result_limit must be at least 1")
        if self.summarization_sample_size < 100:
            errors.append("summarization_sample_size must be at least 100")
        return errors


@dataclass(frozen=True)
class CachingConfig:
    """
    Configuration for query result caching.
    
    Attributes:
        enabled: Whether query caching is enabled.
            Env: QUERY_PIPELINE_CACHE_ENABLED
        default_ttl_seconds: Default TTL for cached results.
            Env: QUERY_PIPELINE_CACHE_TTL
        max_cached_queries: Maximum number of queries to cache.
            Env: QUERY_PIPELINE_CACHE_MAX_QUERIES
        semantic_similarity_threshold: Threshold for semantic cache key matching.
            Env: QUERY_PIPELINE_CACHE_SEMANTIC_THRESHOLD
    """
    enabled: bool = True
    default_ttl_seconds: int = 3600
    max_cached_queries: int = 1000
    semantic_similarity_threshold: float = 0.95
    
    @classmethod
    def from_env(cls) -> "CachingConfig":
        """Load configuration from environment variables."""
        return cls(
            enabled=_get_env_bool("QUERY_PIPELINE_CACHE_ENABLED", True),
            default_ttl_seconds=_get_env_int(
                "QUERY_PIPELINE_CACHE_TTL", 3600
            ),
            max_cached_queries=_get_env_int(
                "QUERY_PIPELINE_CACHE_MAX_QUERIES", 1000
            ),
            semantic_similarity_threshold=_get_env_float(
                "QUERY_PIPELINE_CACHE_SEMANTIC_THRESHOLD", 0.95
            ),
        )
    
    def validate(self) -> list[str]:
        """Validate configuration values."""
        errors = []
        if self.default_ttl_seconds < 60:
            errors.append("default_ttl_seconds must be at least 60")
        if self.max_cached_queries < 10:
            errors.append("max_cached_queries must be at least 10")
        if not 0.0 <= self.semantic_similarity_threshold <= 1.0:
            errors.append("semantic_similarity_threshold must be between 0.0 and 1.0")
        return errors


@dataclass(frozen=True)
class TraceabilityConfig:
    """
    Configuration for query traceability and lineage.
    
    Attributes:
        enabled: Whether traceability is enabled.
            Env: QUERY_PIPELINE_TRACE_ENABLED
        retention_days: Number of days to retain trace records.
            Env: QUERY_PIPELINE_TRACE_RETENTION_DAYS
        include_reasoning: Whether to include reasoning explanations in traces.
            Env: QUERY_PIPELINE_TRACE_INCLUDE_REASONING
        export_formats: Supported export formats (comma-separated).
            Env: QUERY_PIPELINE_TRACE_EXPORT_FORMATS
    """
    enabled: bool = True
    retention_days: int = 90
    include_reasoning: bool = True
    export_formats: tuple[str, ...] = ("json", "csv")
    
    @classmethod
    def from_env(cls) -> "TraceabilityConfig":
        """Load configuration from environment variables."""
        formats_str = os.getenv("QUERY_PIPELINE_TRACE_EXPORT_FORMATS", "json,csv")
        formats = tuple(f.strip() for f in formats_str.split(","))
        return cls(
            enabled=_get_env_bool("QUERY_PIPELINE_TRACE_ENABLED", True),
            retention_days=_get_env_int(
                "QUERY_PIPELINE_TRACE_RETENTION_DAYS", 90
            ),
            include_reasoning=_get_env_bool(
                "QUERY_PIPELINE_TRACE_INCLUDE_REASONING", True
            ),
            export_formats=formats,
        )
    
    def validate(self) -> list[str]:
        """Validate configuration values."""
        errors = []
        if self.retention_days < 1:
            errors.append("retention_days must be at least 1")
        valid_formats = {"json", "csv"}
        for fmt in self.export_formats:
            if fmt not in valid_formats:
                errors.append(f"Invalid export format: {fmt}")
        return errors


@dataclass(frozen=True)
class ConfidenceConfig:
    """
    Configuration for confidence scoring and disclaimers.
    
    Attributes:
        disclaimer_threshold: Confidence below which disclaimers are added.
            Env: QUERY_PIPELINE_CONFIDENCE_DISCLAIMER_THRESHOLD
        file_confidence_weight: Weight for file selection confidence.
            Env: QUERY_PIPELINE_CONFIDENCE_FILE_WEIGHT
        sheet_confidence_weight: Weight for sheet selection confidence.
            Env: QUERY_PIPELINE_CONFIDENCE_SHEET_WEIGHT
        data_confidence_weight: Weight for data retrieval confidence.
            Env: QUERY_PIPELINE_CONFIDENCE_DATA_WEIGHT
    """
    disclaimer_threshold: float = 0.7
    file_confidence_weight: float = 0.3
    sheet_confidence_weight: float = 0.3
    data_confidence_weight: float = 0.4
    
    @classmethod
    def from_env(cls) -> "ConfidenceConfig":
        """Load configuration from environment variables."""
        return cls(
            disclaimer_threshold=_get_env_float(
                "QUERY_PIPELINE_CONFIDENCE_DISCLAIMER_THRESHOLD", 0.7
            ),
            file_confidence_weight=_get_env_float(
                "QUERY_PIPELINE_CONFIDENCE_FILE_WEIGHT", 0.3
            ),
            sheet_confidence_weight=_get_env_float(
                "QUERY_PIPELINE_CONFIDENCE_SHEET_WEIGHT", 0.3
            ),
            data_confidence_weight=_get_env_float(
                "QUERY_PIPELINE_CONFIDENCE_DATA_WEIGHT", 0.4
            ),
        )
    
    def validate(self) -> list[str]:
        """Validate configuration values."""
        errors = []
        if not 0.0 <= self.disclaimer_threshold <= 1.0:
            errors.append("disclaimer_threshold must be between 0.0 and 1.0")
        weights_sum = (
            self.file_confidence_weight + 
            self.sheet_confidence_weight + 
            self.data_confidence_weight
        )
        if abs(weights_sum - 1.0) > 0.01:
            errors.append(f"Confidence weights must sum to 1.0, got {weights_sum}")
        return errors


@dataclass(frozen=True)
class PerformanceConfig:
    """
    Configuration for performance thresholds and monitoring.
    
    Attributes:
        file_selection_timeout_ms: Warning threshold for file selection (ms).
            Env: QUERY_PIPELINE_PERF_FILE_SELECTION_MS
        sheet_selection_timeout_ms: Warning threshold for sheet selection (ms).
            Env: QUERY_PIPELINE_PERF_SHEET_SELECTION_MS
        aggregation_timeout_ms: Warning threshold for aggregation queries (ms).
            Env: QUERY_PIPELINE_PERF_AGGREGATION_MS
        lookup_timeout_ms: Warning threshold for lookup queries (ms).
            Env: QUERY_PIPELINE_PERF_LOOKUP_MS
        chunk_listing_timeout_ms: Warning threshold for chunk listing (ms).
            Env: QUERY_PIPELINE_PERF_CHUNK_LISTING_MS
        log_slow_queries: Whether to log queries exceeding thresholds.
            Env: QUERY_PIPELINE_PERF_LOG_SLOW
    """
    file_selection_timeout_ms: int = 500
    sheet_selection_timeout_ms: int = 200
    aggregation_timeout_ms: int = 2000
    lookup_timeout_ms: int = 1000
    chunk_listing_timeout_ms: int = 500
    log_slow_queries: bool = True
    
    @classmethod
    def from_env(cls) -> "PerformanceConfig":
        """Load configuration from environment variables."""
        return cls(
            file_selection_timeout_ms=_get_env_int(
                "QUERY_PIPELINE_PERF_FILE_SELECTION_MS", 500
            ),
            sheet_selection_timeout_ms=_get_env_int(
                "QUERY_PIPELINE_PERF_SHEET_SELECTION_MS", 200
            ),
            aggregation_timeout_ms=_get_env_int(
                "QUERY_PIPELINE_PERF_AGGREGATION_MS", 2000
            ),
            lookup_timeout_ms=_get_env_int(
                "QUERY_PIPELINE_PERF_LOOKUP_MS", 1000
            ),
            chunk_listing_timeout_ms=_get_env_int(
                "QUERY_PIPELINE_PERF_CHUNK_LISTING_MS", 500
            ),
            log_slow_queries=_get_env_bool(
                "QUERY_PIPELINE_PERF_LOG_SLOW", True
            ),
        )
    
    def validate(self) -> list[str]:
        """Validate configuration values."""
        errors = []
        if self.file_selection_timeout_ms < 100:
            errors.append("file_selection_timeout_ms must be at least 100")
        if self.sheet_selection_timeout_ms < 50:
            errors.append("sheet_selection_timeout_ms must be at least 50")
        return errors


@dataclass(frozen=True)
class BatchConfig:
    """
    Configuration for batch query processing.
    
    Attributes:
        max_queries_per_batch: Maximum queries allowed in a single batch.
            Env: QUERY_PIPELINE_BATCH_MAX_QUERIES
        max_concurrent_queries: Maximum queries to process in parallel.
            Env: QUERY_PIPELINE_BATCH_MAX_CONCURRENT
        batch_timeout_seconds: Timeout for entire batch processing.
            Env: QUERY_PIPELINE_BATCH_TIMEOUT
        continue_on_failure: Whether to continue processing on individual failures.
            Env: QUERY_PIPELINE_BATCH_CONTINUE_ON_FAILURE
    """
    max_queries_per_batch: int = 100
    max_concurrent_queries: int = 10
    batch_timeout_seconds: int = 300
    continue_on_failure: bool = True
    
    @classmethod
    def from_env(cls) -> "BatchConfig":
        """Load configuration from environment variables."""
        return cls(
            max_queries_per_batch=_get_env_int(
                "QUERY_PIPELINE_BATCH_MAX_QUERIES", 100
            ),
            max_concurrent_queries=_get_env_int(
                "QUERY_PIPELINE_BATCH_MAX_CONCURRENT", 10
            ),
            batch_timeout_seconds=_get_env_int(
                "QUERY_PIPELINE_BATCH_TIMEOUT", 300
            ),
            continue_on_failure=_get_env_bool(
                "QUERY_PIPELINE_BATCH_CONTINUE_ON_FAILURE", True
            ),
        )
    
    def validate(self) -> list[str]:
        """Validate configuration values."""
        errors = []
        if self.max_queries_per_batch < 1:
            errors.append("max_queries_per_batch must be at least 1")
        if self.max_concurrent_queries < 1:
            errors.append("max_concurrent_queries must be at least 1")
        if self.batch_timeout_seconds < 30:
            errors.append("batch_timeout_seconds must be at least 30")
        return errors


@dataclass(frozen=True)
class CostEstimationConfig:
    """
    Configuration for query cost estimation.
    
    Attributes:
        enabled: Whether cost estimation is enabled.
            Env: QUERY_PIPELINE_COST_ENABLED
        max_cost_limit: Maximum allowed cost before rejection.
            Env: QUERY_PIPELINE_COST_MAX_LIMIT
        cost_per_file_scan: Cost units per file scanned.
            Env: QUERY_PIPELINE_COST_PER_FILE
        cost_per_1k_rows: Cost units per 1000 rows processed.
            Env: QUERY_PIPELINE_COST_PER_1K_ROWS
        complexity_multiplier: Multiplier for complex queries.
            Env: QUERY_PIPELINE_COST_COMPLEXITY_MULTIPLIER
    """
    enabled: bool = True
    max_cost_limit: float = 100.0
    cost_per_file_scan: float = 1.0
    cost_per_1k_rows: float = 0.5
    complexity_multiplier: float = 1.5
    
    @classmethod
    def from_env(cls) -> "CostEstimationConfig":
        """Load configuration from environment variables."""
        return cls(
            enabled=_get_env_bool("QUERY_PIPELINE_COST_ENABLED", True),
            max_cost_limit=_get_env_float(
                "QUERY_PIPELINE_COST_MAX_LIMIT", 100.0
            ),
            cost_per_file_scan=_get_env_float(
                "QUERY_PIPELINE_COST_PER_FILE", 1.0
            ),
            cost_per_1k_rows=_get_env_float(
                "QUERY_PIPELINE_COST_PER_1K_ROWS", 0.5
            ),
            complexity_multiplier=_get_env_float(
                "QUERY_PIPELINE_COST_COMPLEXITY_MULTIPLIER", 1.5
            ),
        )
    
    def validate(self) -> list[str]:
        """Validate configuration values."""
        errors = []
        if self.max_cost_limit < 1.0:
            errors.append("max_cost_limit must be at least 1.0")
        if self.cost_per_file_scan < 0:
            errors.append("cost_per_file_scan must be non-negative")
        if self.cost_per_1k_rows < 0:
            errors.append("cost_per_1k_rows must be non-negative")
        return errors


@dataclass
class QueryPipelineConfig:
    """
    Main configuration container for the Excel Query Pipeline.
    
    Aggregates all sub-configurations for the query pipeline components.
    All settings can be overridden via environment variables.
    
    Example:
        >>> config = QueryPipelineConfig.from_env()
        >>> print(config.file_selection.auto_select_threshold)
        0.9
        >>> errors = config.validate()
        >>> if errors:
        ...     raise ConfigurationError(f"Invalid config: {errors}")
    """
    file_selection: FileSelectionConfig = field(
        default_factory=FileSelectionConfig
    )
    sheet_selection: SheetSelectionConfig = field(
        default_factory=SheetSelectionConfig
    )
    classification: ClassificationConfig = field(
        default_factory=ClassificationConfig
    )
    processing: ProcessingConfig = field(
        default_factory=ProcessingConfig
    )
    caching: CachingConfig = field(
        default_factory=CachingConfig
    )
    traceability: TraceabilityConfig = field(
        default_factory=TraceabilityConfig
    )
    confidence: ConfidenceConfig = field(
        default_factory=ConfidenceConfig
    )
    performance: PerformanceConfig = field(
        default_factory=PerformanceConfig
    )
    batch: BatchConfig = field(
        default_factory=BatchConfig
    )
    cost_estimation: CostEstimationConfig = field(
        default_factory=CostEstimationConfig
    )
    
    @classmethod
    def from_env(cls) -> "QueryPipelineConfig":
        """
        Load all configuration from environment variables.
        
        Returns:
            QueryPipelineConfig with all sub-configs loaded from env.
        """
        return cls(
            file_selection=FileSelectionConfig.from_env(),
            sheet_selection=SheetSelectionConfig.from_env(),
            classification=ClassificationConfig.from_env(),
            processing=ProcessingConfig.from_env(),
            caching=CachingConfig.from_env(),
            traceability=TraceabilityConfig.from_env(),
            confidence=ConfidenceConfig.from_env(),
            performance=PerformanceConfig.from_env(),
            batch=BatchConfig.from_env(),
            cost_estimation=CostEstimationConfig.from_env(),
        )
    
    def validate(self) -> list[str]:
        """
        Validate all configuration values.
        
        Returns:
            List of validation error messages (empty if valid).
        """
        errors = []
        errors.extend(self.file_selection.validate())
        errors.extend(self.sheet_selection.validate())
        errors.extend(self.classification.validate())
        errors.extend(self.processing.validate())
        errors.extend(self.caching.validate())
        errors.extend(self.traceability.validate())
        errors.extend(self.confidence.validate())
        errors.extend(self.performance.validate())
        errors.extend(self.batch.validate())
        errors.extend(self.cost_estimation.validate())
        return errors
    
    def validate_and_raise(self) -> None:
        """
        Validate configuration and raise exception if invalid.
        
        Raises:
            ConfigurationError: If any validation errors are found.
        """
        errors = self.validate()
        if errors:
            error_msg = "Query pipeline configuration validation failed:\n"
            error_msg += "\n".join(f"  - {err}" for err in errors)
            raise ConfigurationError(error_msg)


# Global configuration instance (no module-level state - created on demand)
_config_instance: Optional[QueryPipelineConfig] = None


def get_query_pipeline_config() -> QueryPipelineConfig:
    """
    Get or create the global query pipeline configuration.
    
    Returns:
        QueryPipelineConfig instance loaded from environment.
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = QueryPipelineConfig.from_env()
    return _config_instance


def reload_query_pipeline_config() -> QueryPipelineConfig:
    """
    Reload configuration from environment variables.
    
    Returns:
        Fresh QueryPipelineConfig instance.
    """
    global _config_instance
    _config_instance = QueryPipelineConfig.from_env()
    return _config_instance
