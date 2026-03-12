"""
Language Detection Service for Excel Extraction.

This module provides language detection capabilities for Excel content during
extraction. It wraps the existing LanguageDetector to provide a clean interface
for the extraction layer.

Supports Requirements:
- 23.1: Detect the primary language of Excel content during extraction
- 23.3: Display detected language for each chunk
"""

import logging
from typing import Any, Optional, Protocol

from src.text_processing.language_detector import Language, LanguageDetector


logger = logging.getLogger(__name__)


class LanguageDetectionProtocol(Protocol):
    """Protocol for language detection services following DIP."""
    
    def detect_language(self, text: str) -> str:
        """
        Detect the primary language of text.
        
        Args:
            text: Text content to analyze.
            
        Returns:
            ISO 639-1 language code (e.g., "en", "th", "mixed", "unknown").
        """
        ...
    
    def get_confidence(self, text: str, language: str) -> float:
        """
        Get confidence score for a specific language detection.
        
        Args:
            text: Text content to analyze.
            language: Language code to check confidence for.
            
        Returns:
            Confidence score between 0.0 and 1.0.
        """
        ...


class ExcelLanguageDetectionService:
    """
    Language detection service for Excel content.
    
    Provides language detection capabilities optimized for Excel data,
    including handling of mixed content, headers, and data cells.
    All dependencies are injected via constructor following DIP.
    
    Attributes:
        _detector: The underlying language detector instance.
        _min_confidence: Minimum confidence threshold for detection.
    
    Example:
        >>> service = ExcelLanguageDetectionService()
        >>> language = service.detect_language("Hello World")
        >>> print(language)  # "en"
    
    Supports Requirement 23.1: Detect the primary language of Excel content.
    """
    
    # Default language when detection fails or content is empty
    DEFAULT_LANGUAGE = "en"
    
    # Minimum text length for reliable detection
    MIN_TEXT_LENGTH = 10
    
    def __init__(
        self,
        detector: Optional[LanguageDetector] = None,
        min_confidence: float = 0.6
    ) -> None:
        """
        Initialize the language detection service.
        
        Args:
            detector: Language detector instance. Creates default if not provided.
            min_confidence: Minimum confidence threshold for detection (0.0-1.0).
        """
        self._detector = detector or LanguageDetector(use_langdetect=True)
        self._min_confidence = min_confidence
        logger.info(
            f"ExcelLanguageDetectionService initialized with "
            f"min_confidence={min_confidence}"
        )
    
    def detect_language(self, text: str) -> str:
        """
        Detect the primary language of text content.
        
        Analyzes the provided text and returns the detected language code.
        Returns default language for empty or very short text.
        
        Args:
            text: Text content to analyze.
            
        Returns:
            ISO 639-1 language code (e.g., "en", "th", "mixed", "unknown").
        
        Supports Requirement 23.1: Detect the primary language of Excel content.
        """
        if not text or len(text.strip()) < self.MIN_TEXT_LENGTH:
            logger.debug(
                f"Text too short for reliable detection ({len(text) if text else 0} chars), "
                f"using default: {self.DEFAULT_LANGUAGE}"
            )
            return self.DEFAULT_LANGUAGE
        
        try:
            detected = self._detector.detect(text, min_confidence=self._min_confidence)
            language_code = detected.value
            
            logger.debug(f"Detected language: {language_code} for text: {text[:50]}...")
            return language_code
            
        except Exception as e:
            logger.warning(f"Language detection failed: {e}, using default")
            return self.DEFAULT_LANGUAGE
    
    def get_confidence(self, text: str, language: str) -> float:
        """
        Get confidence score for a specific language detection.
        
        Args:
            text: Text content to analyze.
            language: Language code to check confidence for.
            
        Returns:
            Confidence score between 0.0 and 1.0.
        """
        if not text or len(text.strip()) < self.MIN_TEXT_LENGTH:
            return 0.0
        
        try:
            # Map language code to Language enum
            language_enum = self._code_to_language(language)
            if language_enum is None:
                return 0.0
            
            return self._detector.get_confidence(text, language_enum)
            
        except Exception as e:
            logger.warning(f"Failed to get language confidence: {e}")
            return 0.0
    
    def detect_from_sheet_data(
        self,
        headers: list[str],
        rows: list[dict[str, Any]],
        sample_size: int = 100
    ) -> str:
        """
        Detect language from sheet data (headers and rows).
        
        Combines headers and sample row data to detect the primary language
        of the sheet content.
        
        Args:
            headers: List of column headers.
            rows: List of row dictionaries.
            sample_size: Maximum number of rows to sample for detection.
            
        Returns:
            ISO 639-1 language code.
        
        Supports Requirement 23.1: Detect the primary language of Excel content.
        """
        # Build text sample from headers and data
        text_parts: list[str] = []
        
        # Add headers
        if headers:
            text_parts.extend(str(h) for h in headers if h)
        
        # Add sample of row data
        for row in rows[:sample_size]:
            for value in row.values():
                if value is not None and isinstance(value, str):
                    text_parts.append(value)
        
        combined_text = " ".join(text_parts)
        return self.detect_language(combined_text)
    
    def detect_from_chunks(self, chunk_texts: list[str]) -> str:
        """
        Detect primary language from multiple chunk texts.
        
        Analyzes multiple chunks and returns the most common detected language.
        
        Args:
            chunk_texts: List of chunk text contents.
            
        Returns:
            ISO 639-1 language code representing the primary language.
        """
        if not chunk_texts:
            return self.DEFAULT_LANGUAGE
        
        # Detect language for each chunk
        language_counts: dict[str, int] = {}
        
        for text in chunk_texts:
            lang = self.detect_language(text)
            language_counts[lang] = language_counts.get(lang, 0) + 1
        
        # Return most common language
        if not language_counts:
            return self.DEFAULT_LANGUAGE
        
        primary_language = max(language_counts, key=language_counts.get)
        logger.debug(
            f"Primary language from {len(chunk_texts)} chunks: {primary_language} "
            f"(counts: {language_counts})"
        )
        return primary_language
    
    def _code_to_language(self, code: str) -> Optional[Language]:
        """
        Convert language code to Language enum.
        
        Args:
            code: ISO 639-1 language code.
            
        Returns:
            Language enum or None if not found.
        """
        code_map = {
            "en": Language.ENGLISH,
            "th": Language.THAI,
            "mixed": Language.MIXED,
            "unknown": Language.UNKNOWN,
        }
        return code_map.get(code.lower())
