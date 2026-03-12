"""Custom exceptions for API"""


class APIException(Exception):
    """Base exception for API errors"""
    def __init__(self, message: str, status_code: int = 500, details: dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(APIException):
    """Authentication related errors"""
    def __init__(self, message: str = "Authentication required", details: dict = None):
        super().__init__(message, status_code=401, details=details)


class AuthorizationError(APIException):
    """Authorization related errors"""
    def __init__(self, message: str = "Access denied", details: dict = None):
        super().__init__(message, status_code=403, details=details)


class NotFoundError(APIException):
    """Resource not found errors"""
    def __init__(self, message: str = "Resource not found", details: dict = None):
        super().__init__(message, status_code=404, details=details)


class ValidationError(APIException):
    """Request validation errors"""
    def __init__(self, message: str = "Invalid request", details: dict = None):
        super().__init__(message, status_code=400, details=details)


class RateLimitError(APIException):
    """Rate limit exceeded errors"""
    def __init__(self, message: str = "Rate limit exceeded", details: dict = None):
        super().__init__(message, status_code=429, details=details)


class ExternalServiceError(APIException):
    """External service errors (Google Drive, LLM, etc.)"""
    def __init__(self, message: str = "External service error", details: dict = None):
        super().__init__(message, status_code=502, details=details)


class IndexingError(APIException):
    """Indexing related errors"""
    def __init__(self, message: str = "Indexing error", details: dict = None):
        super().__init__(message, status_code=500, details=details)


class QueryProcessingError(APIException):
    """Query processing errors"""
    def __init__(self, message: str = "Query processing error", details: dict = None):
        super().__init__(message, status_code=500, details=details)
