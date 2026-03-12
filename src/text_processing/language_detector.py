"""
Language Detection Module

Detects language of text using multiple strategies for accuracy.
Supports Thai, English, and mixed-language content.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
import logging
import re

logger = logging.getLogger(__name__)


class Language(Enum):
    """Supported languages"""
    ENGLISH = "en"
    THAI = "th"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass
class LanguageSpan:
    """Represents a span of text in a specific language"""
    text: str
    language: Language
    start: int
    end: int
    confidence: float


class LanguageDetector:
    """
    Detects language of text using multiple strategies:
    1. Unicode range detection (fast, accurate for Thai)
    2. langdetect library (good for longer text)
    3. Character-based heuristics (fallback)
    """
    
    def __init__(self, use_langdetect: bool = True):
        """
        Initialize language detector
        
        Args:
            use_langdetect: Whether to use langdetect library (requires installation)
        """
        self.use_langdetect = use_langdetect
        self._langdetect_available = False
        
        if use_langdetect:
            try:
                import langdetect
                self._langdetect = langdetect
                self._langdetect_available = True
                logger.info("langdetect library loaded successfully")
            except ImportError:
                logger.warning("langdetect not installed, using Unicode-based detection only")
                self._langdetect_available = False
    
    def detect(self, text: str, min_confidence: float = 0.8) -> Language:
        """
        Detect the primary language of text
        
        Args:
            text: Input text to analyze
            min_confidence: Minimum confidence threshold (0.0 to 1.0)
            
        Returns:
            Detected Language enum
        """
        if not text or not text.strip():
            return Language.UNKNOWN
        
        # Strategy 1: Unicode range detection (fast and accurate for Thai)
        thai_ratio, english_ratio = self._analyze_character_ratios(text)
        
        # If predominantly one language by character count
        if thai_ratio > 0.7:
            logger.debug(f"Detected Thai by character ratio: {thai_ratio:.2f}")
            return Language.THAI
        elif english_ratio > 0.7:
            logger.debug(f"Detected English by character ratio: {english_ratio:.2f}")
            return Language.ENGLISH
        elif thai_ratio > 0.2 and english_ratio > 0.2:
            logger.debug(f"Detected mixed language: Thai={thai_ratio:.2f}, English={english_ratio:.2f}")
            return Language.MIXED
        
        # Strategy 2: Use langdetect for ambiguous cases
        if self._langdetect_available and len(text) > 10:
            try:
                detected_lang = self._langdetect.detect(text)
                confidence = self._langdetect.detect_langs(text)[0].prob
                
                if confidence >= min_confidence:
                    if detected_lang == 'th':
                        logger.debug(f"langdetect confirmed Thai with confidence {confidence:.2f}")
                        return Language.THAI
                    elif detected_lang == 'en':
                        logger.debug(f"langdetect confirmed English with confidence {confidence:.2f}")
                        return Language.ENGLISH
            except Exception as e:
                logger.debug(f"langdetect failed: {e}")
        
        # Strategy 3: Fallback based on character ratios
        if thai_ratio > english_ratio:
            return Language.THAI if thai_ratio > 0.1 else Language.UNKNOWN
        elif english_ratio > thai_ratio:
            return Language.ENGLISH if english_ratio > 0.1 else Language.UNKNOWN
        
        return Language.UNKNOWN
    
    def detect_mixed(self, text: str) -> List[LanguageSpan]:
        """
        Detect language spans in mixed-language text
        
        Args:
            text: Input text that may contain multiple languages
            
        Returns:
            List of LanguageSpan objects representing different language segments
        """
        if not text or not text.strip():
            return []
        
        spans = []
        current_lang = None
        current_start = 0
        current_text = []
        
        for i, char in enumerate(text):
            char_lang = self._detect_char_language(char)
            
            # If language changes or we hit whitespace
            if char_lang != current_lang and current_lang is not None:
                # Save current span
                span_text = ''.join(current_text).strip()
                if span_text:
                    spans.append(LanguageSpan(
                        text=span_text,
                        language=current_lang,
                        start=current_start,
                        end=i,
                        confidence=1.0  # High confidence for Unicode-based detection
                    ))
                current_start = i
                current_text = []
            
            current_lang = char_lang
            current_text.append(char)
        
        # Add final span
        if current_text:
            span_text = ''.join(current_text).strip()
            if span_text:
                spans.append(LanguageSpan(
                    text=span_text,
                    language=current_lang,
                    start=current_start,
                    end=len(text),
                    confidence=1.0
                ))
        
        # Merge adjacent spans of same language
        merged_spans = self._merge_adjacent_spans(spans)
        
        logger.debug(f"Detected {len(merged_spans)} language spans in text")
        return merged_spans
    
    def get_confidence(self, text: str, language: Language) -> float:
        """
        Get confidence score for a specific language detection
        
        Args:
            text: Input text
            language: Language to check confidence for
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        if not text or not text.strip():
            return 0.0
        
        thai_ratio, english_ratio = self._analyze_character_ratios(text)
        
        if language == Language.THAI:
            return thai_ratio
        elif language == Language.ENGLISH:
            return english_ratio
        elif language == Language.MIXED:
            # Mixed confidence is high if both languages present
            return min(thai_ratio + english_ratio, 1.0) if (thai_ratio > 0.2 and english_ratio > 0.2) else 0.0
        
        return 0.0
    
    def _analyze_character_ratios(self, text: str) -> tuple[float, float]:
        """
        Analyze character ratios for Thai and English
        
        Returns:
            Tuple of (thai_ratio, english_ratio)
        """
        thai_chars = 0
        english_chars = 0
        total_chars = 0
        
        for char in text:
            if char.isspace() or not char.isalnum():
                continue
            
            total_chars += 1
            
            # Thai Unicode range: U+0E00 to U+0E7F
            if '\u0E00' <= char <= '\u0E7F':
                thai_chars += 1
            # English letters
            elif char.isalpha() and ord(char) < 128:
                english_chars += 1
        
        if total_chars == 0:
            return 0.0, 0.0
        
        thai_ratio = thai_chars / total_chars
        english_ratio = english_chars / total_chars
        
        return thai_ratio, english_ratio
    
    def _detect_char_language(self, char: str) -> Language:
        """Detect language of a single character"""
        if '\u0E00' <= char <= '\u0E7F':
            return Language.THAI
        elif char.isalpha() and ord(char) < 128:
            return Language.ENGLISH
        else:
            return Language.UNKNOWN
    
    def _merge_adjacent_spans(self, spans: List[LanguageSpan]) -> List[LanguageSpan]:
        """Merge adjacent spans of the same language"""
        if not spans:
            return []
        
        merged = []
        current = spans[0]
        
        for span in spans[1:]:
            if span.language == current.language:
                # Merge with current span
                current = LanguageSpan(
                    text=current.text + ' ' + span.text,
                    language=current.language,
                    start=current.start,
                    end=span.end,
                    confidence=min(current.confidence, span.confidence)
                )
            else:
                merged.append(current)
                current = span
        
        merged.append(current)
        return merged
    
    def is_thai(self, text: str) -> bool:
        """Quick check if text is primarily Thai"""
        return self.detect(text) == Language.THAI
    
    def is_english(self, text: str) -> bool:
        """Quick check if text is primarily English"""
        return self.detect(text) == Language.ENGLISH
    
    def is_mixed(self, text: str) -> bool:
        """Quick check if text contains mixed languages"""
        return self.detect(text) == Language.MIXED
