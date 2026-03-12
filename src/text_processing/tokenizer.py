"""
Tokenization Layer

Provides language-specific tokenization for Thai and English text.
Thai requires special handling due to lack of word boundaries.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
import logging
from .language_detector import Language, LanguageDetector

logger = logging.getLogger(__name__)


class Tokenizer(ABC):
    """Abstract base class for tokenizers"""
    
    @abstractmethod
    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words/tokens
        
        Args:
            text: Input text to tokenize
            
        Returns:
            List of tokens
        """
        pass
    
    @abstractmethod
    def detokenize(self, tokens: List[str]) -> str:
        """
        Reconstruct text from tokens
        
        Args:
            tokens: List of tokens
            
        Returns:
            Reconstructed text
        """
        pass


class EnglishTokenizer(Tokenizer):
    """English tokenizer using spaCy"""
    
    def __init__(self, model: str = "en_core_web_sm"):
        """
        Initialize English tokenizer
        
        Args:
            model: spaCy model name
        """
        try:
            import spacy
            self.nlp = spacy.load(model)
            logger.info(f"Loaded spaCy model: {model}")
        except ImportError:
            logger.error("spaCy not installed. Install with: pip install spacy")
            raise
        except OSError:
            logger.error(f"spaCy model '{model}' not found. Download with: python -m spacy download {model}")
            raise
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize English text"""
        if not text or not text.strip():
            return []
        
        doc = self.nlp(text)
        tokens = [token.text for token in doc if not token.is_space]
        logger.debug(f"Tokenized English text into {len(tokens)} tokens")
        return tokens
    
    def detokenize(self, tokens: List[str]) -> str:
        """Reconstruct English text from tokens"""
        return ' '.join(tokens)


class ThaiTokenizer(Tokenizer):
    """Thai tokenizer using pythainlp"""
    
    def __init__(self, engine: str = "newmm"):
        """
        Initialize Thai tokenizer
        
        Args:
            engine: Tokenization engine ('newmm', 'longest', 'deepcut')
                   - newmm: Maximum Matching (fast, accurate)
                   - longest: Longest matching (fast)
                   - deepcut: Deep learning (slower, more accurate)
        """
        try:
            from pythainlp import word_tokenize
            self.tokenize_func = word_tokenize
            self.engine = engine
            logger.info(f"Initialized Thai tokenizer with engine: {engine}")
        except ImportError:
            logger.error("pythainlp not installed. Install with: pip install pythainlp")
            raise
    
    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize Thai text
        
        Thai has no spaces between words, so we use pythainlp's
        word segmentation algorithms.
        """
        if not text or not text.strip():
            return []
        
        tokens = self.tokenize_func(text, engine=self.engine)
        # Filter out empty tokens and pure whitespace
        tokens = [t for t in tokens if t and not t.isspace()]
        logger.debug(f"Tokenized Thai text into {len(tokens)} tokens")
        return tokens
    
    def detokenize(self, tokens: List[str]) -> str:
        """
        Reconstruct Thai text from tokens
        
        Thai doesn't use spaces between words, but we add them
        for readability in some contexts.
        """
        # Join without spaces (traditional Thai)
        return ''.join(tokens)


class MultilingualTokenizer(Tokenizer):
    """
    Multilingual tokenizer that delegates to language-specific tokenizers
    """
    
    def __init__(self, 
                 english_model: str = "en_core_web_sm",
                 thai_engine: str = "newmm"):
        """
        Initialize multilingual tokenizer
        
        Args:
            english_model: spaCy model for English
            thai_engine: pythainlp engine for Thai
        """
        self.language_detector = LanguageDetector()
        self.english_tokenizer = None
        self.thai_tokenizer = None
        
        # Lazy load tokenizers
        self.english_model = english_model
        self.thai_engine = thai_engine
        
        logger.info("Initialized multilingual tokenizer")
    
    def _get_english_tokenizer(self) -> EnglishTokenizer:
        """Lazy load English tokenizer"""
        if self.english_tokenizer is None:
            self.english_tokenizer = EnglishTokenizer(self.english_model)
        return self.english_tokenizer
    
    def _get_thai_tokenizer(self) -> ThaiTokenizer:
        """Lazy load Thai tokenizer"""
        if self.thai_tokenizer is None:
            self.thai_tokenizer = ThaiTokenizer(self.thai_engine)
        return self.thai_tokenizer
    
    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text using appropriate language-specific tokenizer
        
        For mixed-language text, tokenizes each language segment separately.
        """
        if not text or not text.strip():
            return []
        
        # Detect language
        language = self.language_detector.detect(text)
        
        if language == Language.THAI:
            return self._get_thai_tokenizer().tokenize(text)
        elif language == Language.ENGLISH:
            return self._get_english_tokenizer().tokenize(text)
        elif language == Language.MIXED:
            return self._tokenize_mixed(text)
        else:
            # Unknown language - use simple whitespace tokenization
            logger.warning(f"Unknown language, using whitespace tokenization")
            return text.split()
    
    def _tokenize_mixed(self, text: str) -> List[str]:
        """Tokenize mixed-language text"""
        spans = self.language_detector.detect_mixed(text)
        all_tokens = []
        
        for span in spans:
            if span.language == Language.THAI:
                tokens = self._get_thai_tokenizer().tokenize(span.text)
            elif span.language == Language.ENGLISH:
                tokens = self._get_english_tokenizer().tokenize(span.text)
            else:
                tokens = span.text.split()
            
            all_tokens.extend(tokens)
        
        logger.debug(f"Tokenized mixed text into {len(all_tokens)} tokens")
        return all_tokens
    
    def detokenize(self, tokens: List[str]) -> str:
        """
        Reconstruct text from tokens
        
        Uses simple space joining as we don't know the original language structure.
        """
        return ' '.join(tokens)


class TokenizerFactory:
    """Factory for creating tokenizer instances"""
    
    @staticmethod
    def create(language: str = "multilingual", **kwargs) -> Tokenizer:
        """
        Create a tokenizer instance
        
        Args:
            language: Language type ('english', 'thai', 'multilingual')
            **kwargs: Additional arguments for tokenizer initialization
            
        Returns:
            Tokenizer instance
            
        Raises:
            ValueError: If language is unknown
        """
        language = language.lower()
        
        try:
            if language == "english":
                model = kwargs.get("model", "en_core_web_sm")
                logger.info(f"Creating English tokenizer with model: {model}")
                return EnglishTokenizer(model=model)
            
            elif language == "thai":
                engine = kwargs.get("engine", "newmm")
                logger.info(f"Creating Thai tokenizer with engine: {engine}")
                return ThaiTokenizer(engine=engine)
            
            elif language == "multilingual":
                english_model = kwargs.get("english_model", "en_core_web_sm")
                thai_engine = kwargs.get("thai_engine", "newmm")
                logger.info("Creating multilingual tokenizer")
                return MultilingualTokenizer(
                    english_model=english_model,
                    thai_engine=thai_engine
                )
            
            else:
                raise ValueError(
                    f"Unknown language: {language}. "
                    f"Supported: 'english', 'thai', 'multilingual'"
                )
        
        except Exception as e:
            logger.error(f"Failed to create tokenizer for language '{language}': {e}")
            raise
