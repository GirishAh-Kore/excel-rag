"""
Text Preprocessing Pipeline

Orchestrates language detection, tokenization, and normalization
for preparing text for embedding generation and matching.
"""

from typing import List, Dict, Any, Optional
from functools import lru_cache
import logging

from .language_detector import LanguageDetector, Language
from .tokenizer import TokenizerFactory, Tokenizer
from .normalizer import NormalizerFactory, TextNormalizer, normalize_header

logger = logging.getLogger(__name__)


class TextPreprocessor:
    """
    Text preprocessing pipeline that orchestrates all text processing steps
    
    Provides different preprocessing strategies for:
    - Embedding generation (semantic search)
    - Keyword matching (exact/fuzzy matching)
    - Header normalization (column matching)
    """
    
    def __init__(self,
                 enable_caching: bool = True,
                 cache_size: int = 1000):
        """
        Initialize text preprocessor
        
        Args:
            enable_caching: Whether to cache preprocessing results
            cache_size: Maximum number of cached results
        """
        self.language_detector = LanguageDetector()
        self.tokenizer = TokenizerFactory.create("multilingual")
        
        # Lazy load normalizers
        self._english_normalizer: Optional[TextNormalizer] = None
        self._thai_normalizer: Optional[TextNormalizer] = None
        
        self.enable_caching = enable_caching
        self.cache_size = cache_size
        
        logger.info("Initialized text preprocessor")
    
    def _get_english_normalizer(self) -> TextNormalizer:
        """Lazy load English normalizer"""
        if self._english_normalizer is None:
            self._english_normalizer = NormalizerFactory.create("english")
        return self._english_normalizer
    
    def _get_thai_normalizer(self) -> TextNormalizer:
        """Lazy load Thai normalizer"""
        if self._thai_normalizer is None:
            self._thai_normalizer = NormalizerFactory.create("thai")
        return self._thai_normalizer
    
    @lru_cache(maxsize=1000)
    def preprocess_for_embedding(self, text: str) -> str:
        """
        Preprocess text for embedding generation
        
        Strategy:
        1. Detect language
        2. Tokenize (especially important for Thai)
        3. Normalize (lemmatize English, normalize Thai)
        4. Join back into text
        
        This ensures embeddings capture semantic meaning while
        handling morphological variations.
        
        Args:
            text: Input text
            
        Returns:
            Preprocessed text ready for embedding
        """
        if not text or not text.strip():
            return ""
        
        # Detect language
        language = self.language_detector.detect(text)
        logger.debug(f"Detected language: {language}")
        
        # Tokenize
        tokens = self.tokenizer.tokenize(text)
        
        if not tokens:
            return text.lower().strip()
        
        # Normalize based on language
        if language == Language.THAI:
            normalizer = self._get_thai_normalizer()
            normalized_tokens = normalizer.lemmatize(tokens)
            # Thai: join without spaces
            result = ''.join(normalized_tokens)
        elif language == Language.ENGLISH:
            normalizer = self._get_english_normalizer()
            normalized_tokens = normalizer.lemmatize(tokens)
            # English: join with spaces
            result = ' '.join(normalized_tokens)
        elif language == Language.MIXED:
            # For mixed language, process each part separately
            result = self._preprocess_mixed_for_embedding(text)
        else:
            # Unknown language - basic normalization
            result = ' '.join(tokens).lower()
        
        logger.debug(f"Preprocessed for embedding: '{text[:50]}...' → '{result[:50]}...'")
        return result
    
    def _preprocess_mixed_for_embedding(self, text: str) -> str:
        """Preprocess mixed-language text for embedding"""
        spans = self.language_detector.detect_mixed(text)
        processed_parts = []
        
        for span in spans:
            if span.language == Language.THAI:
                tokens = self.tokenizer.tokenize(span.text)
                normalizer = self._get_thai_normalizer()
                normalized = normalizer.lemmatize(tokens)
                processed_parts.append(''.join(normalized))
            elif span.language == Language.ENGLISH:
                tokens = self.tokenizer.tokenize(span.text)
                normalizer = self._get_english_normalizer()
                normalized = normalizer.lemmatize(tokens)
                processed_parts.append(' '.join(normalized))
            else:
                processed_parts.append(span.text.lower())
        
        return ' '.join(processed_parts)
    
    @lru_cache(maxsize=1000)
    def preprocess_for_matching(self, text: str) -> List[str]:
        """
        Preprocess text for keyword matching
        
        Returns normalized tokens that can be used for exact/fuzzy matching.
        This is used as a fallback when semantic matching confidence is low.
        
        Args:
            text: Input text
            
        Returns:
            List of normalized tokens
        """
        if not text or not text.strip():
            return []
        
        # Detect language
        language = self.language_detector.detect(text)
        
        # Tokenize
        tokens = self.tokenizer.tokenize(text)
        
        if not tokens:
            return []
        
        # Normalize based on language
        if language == Language.THAI:
            normalizer = self._get_thai_normalizer()
            normalized_tokens = normalizer.lemmatize(tokens)
        elif language == Language.ENGLISH:
            normalizer = self._get_english_normalizer()
            normalized_tokens = normalizer.lemmatize(tokens)
        else:
            # Unknown or mixed - basic normalization
            normalized_tokens = [t.lower() for t in tokens]
        
        logger.debug(f"Preprocessed for matching: {len(normalized_tokens)} tokens")
        return normalized_tokens
    
    @lru_cache(maxsize=1000)
    def extract_keywords(self, text: str, min_length: int = 2) -> List[str]:
        """
        Extract important keywords from text
        
        Filters out stop words and short tokens, keeping only
        meaningful terms for search.
        
        Args:
            text: Input text
            min_length: Minimum token length to keep
            
        Returns:
            List of keyword tokens
        """
        tokens = self.preprocess_for_matching(text)
        
        # Filter by length
        keywords = [t for t in tokens if len(t) >= min_length]
        
        # Remove common stop words (basic list)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                     'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
                     'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'would', 'should', 'could', 'may', 'might', 'must', 'can'}
        
        keywords = [k for k in keywords if k.lower() not in stop_words]
        
        logger.debug(f"Extracted {len(keywords)} keywords from text")
        return keywords
    
    def normalize_header_text(self, header: str) -> str:
        """
        Normalize Excel header for matching
        
        Handles edge cases from real data:
        - "First Name – TH " → "first name"
        - "Title - TH" → "title"
        - "Position – EN" → "position"
        
        Args:
            header: Header text
            
        Returns:
            Normalized header
        """
        return normalize_header(header)
    
    def detect_language(self, text: str) -> Language:
        """
        Detect language of text
        
        Args:
            text: Input text
            
        Returns:
            Detected Language
        """
        return self.language_detector.detect(text)
    
    def get_preprocessing_info(self, text: str) -> Dict[str, Any]:
        """
        Get detailed preprocessing information for debugging
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with preprocessing details
        """
        language = self.language_detector.detect(text)
        tokens = self.tokenizer.tokenize(text)
        keywords = self.extract_keywords(text)
        preprocessed_embedding = self.preprocess_for_embedding(text)
        preprocessed_matching = self.preprocess_for_matching(text)
        
        return {
            "original": text,
            "language": language.value,
            "tokens": tokens,
            "token_count": len(tokens),
            "keywords": keywords,
            "keyword_count": len(keywords),
            "preprocessed_for_embedding": preprocessed_embedding,
            "preprocessed_for_matching": preprocessed_matching,
            "confidence": self.language_detector.get_confidence(text, language)
        }
    
    def clear_cache(self):
        """Clear preprocessing cache"""
        if self.enable_caching:
            self.preprocess_for_embedding.cache_clear()
            self.preprocess_for_matching.cache_clear()
            self.extract_keywords.cache_clear()
            logger.info("Cleared preprocessing cache")
