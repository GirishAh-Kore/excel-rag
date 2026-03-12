"""
Content extraction module for Excel files.

This module provides functionality to extract structured data from Excel files
including cell values, formulas, formatting, pivot tables, and charts.

Supports multiple extraction strategies:
- openpyxl (default, fast, local)
- Google Gemini (multimodal, optional)
- LlamaParse (document understanding, optional)

Also provides LLM-based sheet summarization for improved disambiguation.
"""

from src.extraction.configurable_extractor import ConfigurableExtractor
from src.extraction.content_extractor import (
    ContentExtractor,
    CorruptedFileError,
    ExtractionError,
    MemoryError,
    UnsupportedFormatError,
)
from src.extraction.extraction_strategy import (
    ExtractionConfig,
    ExtractionQuality,
    ExtractionStrategy,
)
from src.extraction.quality_scorer import (
    ExtractionQualityScorer,
    QualityAssessment,
    QualityScorerConfig,
)
from src.extraction.sheet_summarizer import SheetSummarizer
from src.extraction.streaming import (
    ChunkAggregator,
    StreamingChunk,
    StreamingExcelExtractor,
    StreamingExtractionConfig,
    StreamingExtractionResult,
    create_streaming_extractor,
)
from src.extraction.incremental import (
    ChecksumCalculator,
    ChunkChangeResult,
    ChunkChangeType,
    ChunkChecksum,
    FileChangeResult,
    FileChangeType,
    FileChecksum,
    IncrementalIndexingResult,
    IncrementalIndexingService,
    InMemoryChecksumStore,
    create_incremental_indexing_service,
)

__all__ = [
    # Core extractors
    "ContentExtractor",
    "ConfigurableExtractor",
    
    # Exceptions
    "ExtractionError",
    "CorruptedFileError",
    "UnsupportedFormatError",
    "MemoryError",
    
    # Configuration
    "ExtractionConfig",
    "ExtractionStrategy",
    "ExtractionQuality",
    
    # Quality scoring
    "ExtractionQualityScorer",
    "QualityScorerConfig",
    "QualityAssessment",
    
    # Summarization
    "SheetSummarizer",
    
    # Streaming extraction
    "StreamingExcelExtractor",
    "StreamingExtractionConfig",
    "StreamingExtractionResult",
    "StreamingChunk",
    "ChunkAggregator",
    "create_streaming_extractor",
    
    # Incremental indexing
    "IncrementalIndexingService",
    "IncrementalIndexingResult",
    "FileChecksum",
    "ChunkChecksum",
    "FileChangeResult",
    "ChunkChangeResult",
    "FileChangeType",
    "ChunkChangeType",
    "ChecksumCalculator",
    "InMemoryChecksumStore",
    "create_incremental_indexing_service",
]
