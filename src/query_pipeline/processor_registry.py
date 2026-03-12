"""
Query Processor Registry Module.

This module implements a registry pattern for query processors, following the
Open/Closed Principle. New processors can be registered without modifying
existing code using the @register decorator.

Key Components:
- QueryProcessorRegistry: Central registry for query processors
- register: Decorator for registering processor classes

Supports Requirements 7.1, 8.1, 9.1, 10.1.

Example:
    >>> from src.query_pipeline.processor_registry import QueryProcessorRegistry, register
    >>> from src.models.query_pipeline import QueryType
    >>>
    >>> @register(QueryType.AGGREGATION)
    ... class MyAggregationProcessor(BaseQueryProcessor):
    ...     def process(self, query, data, classification):
    ...         ...
    >>>
    >>> processor = QueryProcessorRegistry.get_processor(
    ...     QueryType.AGGREGATION,
    ...     llm_service=llm_svc
    ... )
"""

import logging
from threading import Lock
from typing import Any, Callable, Optional, Type, TYPE_CHECKING

from src.exceptions import ProcessingError
from src.models.query_pipeline import QueryType

if TYPE_CHECKING:
    from src.query_pipeline.processors.base import BaseQueryProcessor

logger = logging.getLogger(__name__)


class QueryProcessorRegistry:
    """
    Registry for query processors following Open/Closed Principle.
    
    New processors can be registered without modifying existing code.
    The registry is thread-safe and supports dependency injection when
    creating processor instances.
    
    Implements Requirements 7.1, 8.1, 9.1, 10.1.
    
    Example:
        >>> # Registration (typically done in processor module)
        >>> QueryProcessorRegistry.register_processor(
        ...     QueryType.AGGREGATION,
        ...     AggregationProcessor
        ... )
        >>>
        >>> # Retrieval with dependency injection
        >>> processor = QueryProcessorRegistry.get_processor(
        ...     QueryType.AGGREGATION,
        ...     llm_service=my_llm_service,
        ...     config=my_config
        ... )
    """
    
    _registry: dict[QueryType, Type["BaseQueryProcessor"]] = {}
    _lock: Lock = Lock()
    
    @classmethod
    def register_processor(
        cls,
        query_type: QueryType,
        processor_class: Type["BaseQueryProcessor"]
    ) -> None:
        """
        Register a processor class for a query type.
        
        Args:
            query_type: The query type this processor handles.
            processor_class: The processor class to register.
            
        Raises:
            ValueError: If query_type is invalid or processor_class is None.
            ProcessingError: If a processor is already registered for this type.
        """
        if query_type is None:
            raise ValueError("query_type cannot be None")
        if processor_class is None:
            raise ValueError("processor_class cannot be None")
        
        with cls._lock:
            if query_type in cls._registry:
                existing = cls._registry[query_type].__name__
                logger.warning(
                    f"Overwriting existing processor {existing} for "
                    f"{query_type.value} with {processor_class.__name__}"
                )
            
            cls._registry[query_type] = processor_class
            logger.info(
                f"Registered {processor_class.__name__} for "
                f"query type {query_type.value}"
            )
    
    @classmethod
    def get_processor(
        cls,
        query_type: QueryType,
        **dependencies: Any
    ) -> "BaseQueryProcessor":
        """
        Get a processor instance for the specified query type.
        
        Creates a new instance of the registered processor class,
        injecting the provided dependencies.
        
        Args:
            query_type: The query type to get a processor for.
            **dependencies: Dependencies to inject into the processor.
            
        Returns:
            An instance of the registered processor class.
            
        Raises:
            ProcessingError: If no processor is registered for the query type.
        """
        with cls._lock:
            if query_type not in cls._registry:
                available = [qt.value for qt in cls._registry.keys()]
                raise ProcessingError(
                    f"No processor registered for query type '{query_type.value}'",
                    details={
                        "query_type": query_type.value,
                        "available_types": available
                    }
                )
            
            processor_class = cls._registry[query_type]
        
        try:
            processor = processor_class(**dependencies)
            logger.debug(
                f"Created {processor_class.__name__} instance for "
                f"query type {query_type.value}"
            )
            return processor
        except TypeError as e:
            raise ProcessingError(
                f"Failed to create processor for '{query_type.value}': {e}",
                details={
                    "query_type": query_type.value,
                    "processor_class": processor_class.__name__,
                    "error": str(e)
                }
            )
    
    @classmethod
    def has_processor(cls, query_type: QueryType) -> bool:
        """
        Check if a processor is registered for the query type.
        
        Args:
            query_type: The query type to check.
            
        Returns:
            True if a processor is registered, False otherwise.
        """
        with cls._lock:
            return query_type in cls._registry
    
    @classmethod
    def get_registered_types(cls) -> list[QueryType]:
        """
        Get all registered query types.
        
        Returns:
            List of query types that have registered processors.
        """
        with cls._lock:
            return list(cls._registry.keys())
    
    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered processors.
        
        Primarily used for testing to reset registry state.
        """
        with cls._lock:
            cls._registry.clear()
            logger.debug("Cleared all registered processors")


def register(query_type: QueryType) -> Callable[[Type["BaseQueryProcessor"]], Type["BaseQueryProcessor"]]:
    """
    Decorator to register a processor class for a query type.
    
    This decorator provides a clean way to register processors at
    class definition time, following the Open/Closed Principle.
    
    Args:
        query_type: The query type this processor handles.
        
    Returns:
        Decorator function that registers the class.
        
    Example:
        >>> @register(QueryType.AGGREGATION)
        ... class AggregationProcessor(BaseQueryProcessor):
        ...     def process(self, query, data, classification):
        ...         ...
    """
    def decorator(processor_class: Type["BaseQueryProcessor"]) -> Type["BaseQueryProcessor"]:
        QueryProcessorRegistry.register_processor(query_type, processor_class)
        return processor_class
    
    return decorator
