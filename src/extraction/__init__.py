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
from src.extraction.sheet_summarizer import SheetSummarizer

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
    
    # Summarization
    "SheetSummarizer",
]
