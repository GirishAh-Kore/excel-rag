"""
Text Normalization Layer

Handles morphological variations, lemmatization, and language-specific normalization.
Critical for matching "expense" vs "expenses", "sold" vs "selling", etc.
"""

from abc import ABC, abstractmethod
from typing import List
import logging
import re

logger = logging.getLogger(__name__)


class TextNormalizer(ABC):
    """Abstract base class for text normalizers"""
    
    @abstractmethod
    def normalize(self, text: str) -> str:
        """
        Normalize text (lowercase, whitespace, etc.)
        
        Args:
            text: Input text
            
        Returns:
            Normalized text
        """
        pass
    
    @abstractmethod
    def lemmatize(self, tokens: List[str]) -> List[str]:
        """
        Lemmatize tokens to base form
        
        Args:
            tokens: List of tokens
            
        Returns:
            List of lemmatized tokens
        """
        pass
    
    @abstractmethod
    def stem(self, tokens: List[str]) -> List[str]:
        """
        Stem tokens (more aggressive than lemmatization)
        
        Args:
            tokens: List of tokens
            
        Returns:
            List of stemmed tokens
        """
        pass


class EnglishNormalizer(TextNormalizer):
    """
    English text normalizer with lemmatization support
    
    Handles:
    - Plurals: expenses → expense
    - Tenses: sold/selling/sells → sell
    - Case normalization
    - Whitespace normalization
    """
    
    def __init__(self, model: str = "en_core_web_sm"):
        """
        Initialize English normalizer
        
        Args:
            model: spaCy model name
        """
        try:
            import spacy
            self.nlp = spacy.load(model)
            logger.info(f"Loaded spaCy model for normalization: {model}")
        except ImportError:
            logger.error("spaCy not installed. Install with: pip install spacy")
            raise
        except OSError:
            logger.error(f"spaCy model '{model}' not found. Download with: python -m spacy download {model}")
            raise
    
    def normalize(self, text: str) -> str:
        """
        Normalize English text
        
        - Lowercase
        - Normalize whitespace
        - Remove extra punctuation
        - Normalize dashes (-, –, —)
        """
        if not text:
            return ""
        
        # Lowercase
        text = text.lower()
        
        # Normalize different types of dashes to standard hyphen
        text = re.sub(r'[–—]', '-', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def lemmatize(self, tokens: List[str]) -> List[str]:
        """
        Lemmatize English tokens
        
        Examples:
        - expenses → expense
        - sold → sell
        - selling → sell
        - categories → category
        - running → run
        """
        if not tokens:
            return []
        
        # Join tokens and process with spaCy
        text = ' '.join(tokens)
        doc = self.nlp(text)
        
        lemmas = [token.lemma_.lower() for token in doc if not token.is_space]
        logger.debug(f"Lemmatized {len(tokens)} tokens")
        return lemmas
    
    def stem(self, tokens: List[str]) -> List[str]:
        """
        Stem English tokens using Porter stemmer
        
        More aggressive than lemmatization.
        """
        try:
            from nltk.stem import PorterStemmer
            stemmer = PorterStemmer()
            stems = [stemmer.stem(token.lower()) for token in tokens]
            logger.debug(f"Stemmed {len(tokens)} tokens")
            return stems
        except ImportError:
            logger.warning("NLTK not installed, falling back to lemmatization")
            return self.lemmatize(tokens)
    
    def normalize_for_matching(self, text: str) -> str:
        """
        Normalize text specifically for cell/header matching
        
        - Lowercase
        - Lemmatize
        - Remove punctuation
        - Normalize whitespace
        """
        # Basic normalization
        text = self.normalize(text)
        
        # Tokenize and lemmatize
        doc = self.nlp(text)
        lemmas = [token.lemma_ for token in doc if token.is_alpha]
        
        return ' '.join(lemmas)


class ThaiNormalizer(TextNormalizer):
    """
    Thai text normalizer
    
    Thai is simpler than English:
    - No plurals
    - No verb conjugation
    - But needs: digit normalization, whitespace handling
    """
    
    def __init__(self):
        """Initialize Thai normalizer"""
        try:
            from pythainlp.util import normalize as thai_normalize
            from pythainlp.util import thai_digit_to_arabic
            self.thai_normalize = thai_normalize
            self.thai_digit_to_arabic = thai_digit_to_arabic
            logger.info("Initialized Thai normalizer")
        except ImportError:
            logger.error("pythainlp not installed. Install with: pip install pythainlp")
            raise
    
    def normalize(self, text: str) -> str:
        """
        Normalize Thai text
        
        - Convert Thai digits to Arabic (๐-๙ → 0-9)
        - Normalize whitespace
        - Remove extra spaces
        - Normalize dashes
        """
        if not text:
            return ""
        
        # Use pythainlp's normalize function
        text = self.thai_normalize(text)
        
        # Convert Thai digits to Arabic
        text = self.thai_digit_to_arabic(text)
        
        # Normalize different types of dashes
        text = re.sub(r'[–—]', '-', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def lemmatize(self, tokens: List[str]) -> List[str]:
        """
        Lemmatize Thai tokens
        
        Thai doesn't have morphological variations like English,
        so this is mostly a pass-through with normalization.
        """
        # Thai doesn't need lemmatization (no plurals, no tenses)
        # Just normalize each token
        return [self.normalize(token) for token in tokens]
    
    def stem(self, tokens: List[str]) -> List[str]:
        """
        Stem Thai tokens
        
        Thai doesn't have stemming in the traditional sense.
        """
        # Thai doesn't need stemming
        return self.lemmatize(tokens)
    
    def normalize_for_matching(self, text: str) -> str:
        """
        Normalize Thai text for matching
        
        Simpler than English since no morphological variations.
        """
        return self.normalize(text)


class NormalizerFactory:
    """Factory for creating normalizer instances"""
    
    @staticmethod
    def create(language: str, **kwargs) -> TextNormalizer:
        """
        Create a normalizer instance
        
        Args:
            language: Language type ('english', 'thai')
            **kwargs: Additional arguments for normalizer initialization
            
        Returns:
            TextNormalizer instance
            
        Raises:
            ValueError: If language is unknown
        """
        language = language.lower()
        
        try:
            if language == "english":
                model = kwargs.get("model", "en_core_web_sm")
                logger.info(f"Creating English normalizer with model: {model}")
                return EnglishNormalizer(model=model)
            
            elif language == "thai":
                logger.info("Creating Thai normalizer")
                return ThaiNormalizer()
            
            else:
                raise ValueError(
                    f"Unknown language: {language}. "
                    f"Supported: 'english', 'thai'"
                )
        
        except Exception as e:
            logger.error(f"Failed to create normalizer for language '{language}': {e}")
            raise


# Utility functions for common normalization tasks

def normalize_header(header: str) -> str:
    """
    Normalize Excel header for matching
    
    Handles edge cases found in real data:
    - Extra whitespace: "First Name – TH " → "first name th"
    - Different dashes: "Title - TH" vs "Title – EN"
    - Case variations: "REVENUE" → "revenue"
    """
    if not header:
        return ""
    
    # Lowercase
    header = header.lower()
    
    # Normalize all types of dashes to space
    header = re.sub(r'[-–—]', ' ', header)
    
    # Remove common suffixes
    header = re.sub(r'\s+(th|en)\s*$', '', header)
    
    # Normalize whitespace
    header = re.sub(r'\s+', ' ', header)
    header = header.strip()
    
    return header


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text"""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def normalize_dashes(text: str) -> str:
    """Normalize different types of dashes"""
    if not text:
        return ""
    return re.sub(r'[–—]', '-', text)
