"""
RAG System Exception Hierarchy

Provides a consistent exception hierarchy for the entire RAG system.
All custom exceptions should inherit from RAGSystemError.

Usage:
    from src.exceptions import ExtractionError, QueryError
    
    raise ExtractionError("Failed to extract data from file")
"""


class RAGSystemError(Exception):
    """
    Base exception for all RAG system errors.
    
    All custom exceptions in the system should inherit from this class
    to enable consistent error handling and logging.
    """
    
    def __init__(self, message: str, details: dict = None):
        """
        Initialize RAGSystemError.
        
        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(RAGSystemError):
    """
    Configuration-related errors.
    
    Raised when:
    - Required configuration is missing
    - Configuration values are invalid
    - Environment variables are not set in production
    """
    pass


class ExtractionError(RAGSystemError):
    """
    Document extraction errors.
    
    Raised when:
    - File cannot be read or parsed
    - Extraction strategy fails
    - File format is unsupported
    """
    pass


class CorruptedFileError(ExtractionError):
    """
    Corrupted or unreadable file errors.
    
    Raised when:
    - File is corrupted and cannot be opened
    - File structure is invalid
    """
    pass


class QueryError(RAGSystemError):
    """
    Query processing errors.
    
    Raised when:
    - Query analysis fails
    - Semantic search fails
    - Answer generation fails
    """
    pass


class ClarificationError(QueryError):
    """
    Clarification flow errors.
    
    Raised when:
    - Clarification generation fails
    - Invalid clarification response
    """
    pass


class ProviderError(RAGSystemError):
    """
    Service provider errors.
    
    Raised when:
    - Unknown provider requested
    - Provider initialization fails
    - Provider API call fails
    """
    pass


class LLMProviderError(ProviderError):
    """LLM service provider errors."""
    pass


class EmbeddingProviderError(ProviderError):
    """Embedding service provider errors."""
    pass


class VectorStoreError(ProviderError):
    """Vector store provider errors."""
    pass


class CacheError(ProviderError):
    """Cache service provider errors."""
    pass


class AuthenticationError(RAGSystemError):
    """
    Authentication errors.
    
    Raised when:
    - Authentication fails
    - Token is invalid or expired
    - Insufficient permissions
    """
    pass


class GoogleDriveError(RAGSystemError):
    """
    Google Drive API errors.
    
    Raised when:
    - Drive API call fails
    - File access denied
    - Rate limit exceeded
    """
    pass


class IndexingError(RAGSystemError):
    """
    Indexing pipeline errors.
    
    Raised when:
    - Indexing job fails
    - Vector storage fails
    - Metadata storage fails
    """
    pass


class SessionError(RAGSystemError):
    """
    Session management errors.
    
    Raised when:
    - Session not found
    - Session expired
    - Session data corrupted
    """
    pass


class ValidationError(RAGSystemError):
    """
    Input validation errors.
    
    Raised when:
    - Request data is invalid
    - Required fields are missing
    - Data format is incorrect
    """
    pass


# =============================================================================
# Query Pipeline Exceptions
# =============================================================================


class ChunkViewerError(RAGSystemError):
    """
    Chunk viewer errors.
    
    Raised when:
    - Chunk retrieval fails
    - Chunk metadata is missing or corrupted
    - Chunk version operations fail
    - Chunk feedback submission fails
    
    Requirements: 12.1, 12.5
    """
    pass


class TraceError(RAGSystemError):
    """
    Query trace errors.
    
    Raised when:
    - Trace recording fails
    - Trace retrieval fails
    - Trace export fails
    - Trace storage is unavailable
    
    Requirements: 12.5
    """
    pass


class LineageError(RAGSystemError):
    """
    Data lineage errors.
    
    Raised when:
    - Lineage record creation fails
    - Lineage retrieval fails
    - Source data verification fails
    - Lineage chain is broken or incomplete
    
    Requirements: 12.5
    """
    pass


class ClassificationError(RAGSystemError):
    """
    Query classification errors.
    
    Raised when:
    - Query type cannot be determined
    - Classification confidence is too low
    - LLM classification service fails
    
    Requirements: 12.5
    """
    pass


class ProcessingError(RAGSystemError):
    """
    Query processing errors.
    
    Raised when:
    - Aggregation fails due to data type issues
    - Lookup finds no matching data
    - Summarization generation fails
    - Comparison entities are incompatible
    
    Requirements: 12.3, 12.5
    """
    pass


class SelectionError(RAGSystemError):
    """
    File or sheet selection errors.
    
    Raised when:
    - No indexed files are available
    - File selection fails due to ambiguous data
    - Sheet selection fails due to ambiguous data
    - Referenced file or sheet does not exist
    
    Requirements: 12.1, 12.2, 12.4
    """
    pass


class BatchError(RAGSystemError):
    """
    Batch query processing errors.
    
    Raised when:
    - Batch query submission fails
    - Batch size exceeds limit
    - Batch processing times out
    - Batch status retrieval fails
    
    Requirements: 12.5
    """
    pass


class TemplateError(RAGSystemError):
    """
    Query template errors.
    
    Raised when:
    - Template creation fails
    - Template parameter substitution fails
    - Template execution fails
    - Template not found
    
    Requirements: 12.5
    """
    pass


class WebhookError(RAGSystemError):
    """
    Webhook errors.
    
    Raised when:
    - Webhook registration fails
    - Webhook delivery fails after retries
    - Webhook URL is invalid
    - Webhook event type is unsupported
    
    Requirements: 12.5
    """
    pass


class ExportError(RAGSystemError):
    """
    Export errors.
    
    Raised when:
    - Export format is unsupported
    - Export data is invalid or empty
    - Export file generation fails
    - Scheduled export creation or execution fails
    
    Requirements: 26.1, 26.2, 26.3, 26.4, 26.5
    """
    pass
