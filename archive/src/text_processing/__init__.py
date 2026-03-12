"""
Text processing module for multi-language support

Provides language detection, tokenization, normalization, and preprocessing
for Thai and English text.
"""

from .language_detector import LanguageDetector, Language, LanguageSpan
from .tokenizer import Tokenizer, EnglishTokenizer, ThaiTokenizer, MultilingualTokenizer, TokenizerFactory
from .normalizer import (
    TextNormalizer, 
    EnglishNormalizer, 
    ThaiNormalizer, 
    NormalizerFactory,
    normalize_header,
    normalize_whitespace,
    normalize_dashes
)
from .preprocessor import TextPreprocessor

__all__ = [
    # Language Detection
    'LanguageDetector',
    'Language',
    'LanguageSpan',
    # Tokenization
    'Tokenizer',
    'EnglishTokenizer',
    'ThaiTokenizer',
    'MultilingualTokenizer',
    'TokenizerFactory',
    # Normalization
    'TextNormalizer',
    'EnglishNormalizer',
    'ThaiNormalizer',
    'NormalizerFactory',
    'normalize_header',
    'normalize_whitespace',
    'normalize_dashes',
    # Preprocessing Pipeline
    'TextPreprocessor',
]
