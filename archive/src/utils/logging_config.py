"""Structured logging configuration for the application"""

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Optional
from pythonjsonlogger import jsonlogger


# Log directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Log levels based on environment
ENV = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if ENV == "development" else "INFO")


class CorrelationIdFilter(logging.Filter):
    """Filter to add correlation ID to log records"""
    
    def filter(self, record):
        from src.api.middleware import correlation_id_var
        try:
            record.correlation_id = correlation_id_var.get()
        except LookupError:
            record.correlation_id = ""
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record['timestamp'] = self.formatTime(record, self.datefmt)
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        
        # Add correlation ID if available
        if hasattr(record, 'correlation_id') and record.correlation_id:
            log_record['correlation_id'] = record.correlation_id
        
        # Add any extra fields from the log call
        if hasattr(record, 'extra_fields'):
            log_record.update(record.extra_fields)


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: Optional[str] = None,
    json_format: bool = True
) -> logging.Logger:
    """
    Set up a logger with structured logging
    
    Args:
        name: Logger name (typically __name__)
        log_file: Optional specific log file name (without path)
        level: Optional log level override
        json_format: Whether to use JSON formatting (default True)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Set log level
    log_level = level or LOG_LEVEL
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Add correlation ID filter
    correlation_filter = CorrelationIdFilter()
    
    # Console handler (always add)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.addFilter(correlation_filter)
    
    if json_format and ENV == "production":
        # JSON format for production
        console_formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
    else:
        # Human-readable format for development
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (if log_file specified)
    if log_file:
        file_path = LOG_DIR / log_file
        
        # Rotating file handler (daily rotation, keep 30 days)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=file_path,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.addFilter(correlation_filter)
        
        if json_format:
            file_formatter = CustomJsonFormatter(
                '%(timestamp)s %(level)s %(name)s %(message)s'
            )
        else:
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def setup_component_loggers():
    """Set up loggers for different components with separate log files"""
    
    # API logger
    api_logger = setup_logger(
        'src.api',
        log_file='api.log',
        json_format=True
    )
    
    # Indexing logger
    indexing_logger = setup_logger(
        'src.indexing',
        log_file='indexing.log',
        json_format=True
    )
    
    # Query logger
    query_logger = setup_logger(
        'src.query',
        log_file='queries.log',
        json_format=True
    )
    
    # Error logger (ERROR and above only)
    error_logger = setup_logger(
        'errors',
        log_file='errors.log',
        level='ERROR',
        json_format=True
    )
    
    # Add error handler to root logger to catch all errors
    root_logger = logging.getLogger()
    error_handler = logging.handlers.TimedRotatingFileHandler(
        filename=LOG_DIR / 'errors.log',
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.addFilter(CorrelationIdFilter())
    error_handler.setFormatter(CustomJsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    ))
    root_logger.addHandler(error_handler)
    
    return {
        'api': api_logger,
        'indexing': indexing_logger,
        'query': query_logger,
        'error': error_logger
    }


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module
    
    Args:
        name: Module name (typically __name__)
    
    Returns:
        Logger instance
    """
    # Determine which log file to use based on module name
    log_file = None
    if 'api' in name:
        log_file = 'api.log'
    elif 'indexing' in name:
        log_file = 'indexing.log'
    elif 'query' in name:
        log_file = 'queries.log'
    
    return setup_logger(name, log_file=log_file)


# Initialize component loggers on import
_component_loggers = None


def init_logging():
    """Initialize all component loggers"""
    global _component_loggers
    if _component_loggers is None:
        _component_loggers = setup_component_loggers()
    return _component_loggers


# Convenience function for logging with extra context
def log_with_context(logger: logging.Logger, level: str, message: str, **context):
    """
    Log a message with additional context fields
    
    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **context: Additional context fields to include in log
    """
    log_func = getattr(logger, level.lower())
    
    # Create a log record with extra fields
    extra = {'extra_fields': context}
    log_func(message, extra=extra)
