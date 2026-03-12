"""
Query processing components for the Google Drive Excel RAG system.

This package contains modules for analyzing queries, searching for relevant data,
managing conversation context, generating clarifications, selecting files and sheets,
and orchestrating the complete query processing pipeline.
"""

from src.query.query_analyzer import QueryAnalyzer, QueryAnalysis
from src.query.semantic_searcher import SemanticSearcher, SearchResult, SearchResults
from src.query.conversation_manager import ConversationManager, SessionData
from src.query.clarification_generator import (
    ClarificationGenerator,
    ClarificationOption,
    ClarificationRequest
)
from src.query.query_engine import QueryEngine
from src.query.file_selector import FileSelector, FileSelection
from src.query.sheet_selector import SheetSelector, ScoredSheet, MultiSheetSelection
from src.query.date_parser import DateParser, ParsedDate
from src.query.preference_manager import PreferenceManager
from src.query.comparison_engine import ComparisonEngine
from src.query.sheet_aligner import SheetAligner
from src.query.difference_calculator import DifferenceCalculator, TrendDirection
from src.query.comparison_formatter import ComparisonFormatter
from src.query.prompt_builder import PromptBuilder, AnswerType, Language
from src.query.data_formatter import DataFormatter
from src.query.citation_generator import CitationGenerator, Citation
from src.query.confidence_scorer import ConfidenceScorer, ConfidenceBreakdown
from src.query.no_results_handler import NoResultsHandler, NoResultsResponse
from src.query.answer_generator import AnswerGenerator

__all__ = [
    "QueryAnalyzer",
    "QueryAnalysis",
    "SemanticSearcher",
    "SearchResult",
    "SearchResults",
    "ConversationManager",
    "SessionData",
    "ClarificationGenerator",
    "ClarificationOption",
    "ClarificationRequest",
    "QueryEngine",
    "FileSelector",
    "FileSelection",
    "SheetSelector",
    "ScoredSheet",
    "MultiSheetSelection",
    "DateParser",
    "ParsedDate",
    "PreferenceManager",
    "ComparisonEngine",
    "SheetAligner",
    "DifferenceCalculator",
    "TrendDirection",
    "ComparisonFormatter",
    "PromptBuilder",
    "AnswerType",
    "Language",
    "DataFormatter",
    "CitationGenerator",
    "Citation",
    "ConfidenceScorer",
    "ConfidenceBreakdown",
    "NoResultsHandler",
    "NoResultsResponse",
    "AnswerGenerator",
]
