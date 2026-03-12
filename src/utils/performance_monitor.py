"""
Performance logging and monitoring for the query pipeline.

This module provides performance monitoring capabilities including timing
decorators, threshold-based warnings, and performance metrics collection
for the Excel query pipeline operations.

Supports Requirements:
- 15.1: File selection results within 500ms for up to 1000 indexed files
- 15.2: Sheet selection results within 200ms for files with up to 50 sheets
- 15.3: Aggregation query results within 2 seconds for up to 100,000 rows
- 15.4: Lookup query results within 1 second for up to 100,000 rows
- 15.5: Chunk listings within 500ms for files with up to 1000 chunks
- 15.6: Log warnings when performance thresholds exceeded
"""

import functools
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

from src.utils.metrics import (
    MetricsCollector,
    get_metrics_collector,
    record_timer,
)


logger = logging.getLogger(__name__)


# =============================================================================
# Type Variables
# =============================================================================

F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# Constants and Configuration
# =============================================================================

class OperationType(str, Enum):
    """Types of operations being monitored."""
    FILE_SELECTION = "file_selection"
    SHEET_SELECTION = "sheet_selection"
    QUERY_CLASSIFICATION = "query_classification"
    AGGREGATION = "aggregation"
    LOOKUP = "lookup"
    SUMMARIZATION = "summarization"
    COMPARISON = "comparison"
    CHUNK_LISTING = "chunk_listing"
    CHUNK_SEARCH = "chunk_search"
    ANSWER_GENERATION = "answer_generation"
    TRACE_RECORDING = "trace_recording"
    CACHE_LOOKUP = "cache_lookup"
    EXTRACTION = "extraction"
    INDEXING = "indexing"


# Performance thresholds in milliseconds (from Requirements 15.x)
DEFAULT_THRESHOLDS: dict[OperationType, float] = {
    OperationType.FILE_SELECTION: 500.0,      # 15.1: <500ms
    OperationType.SHEET_SELECTION: 200.0,     # 15.2: <200ms
    OperationType.AGGREGATION: 2000.0,        # 15.3: <2s
    OperationType.LOOKUP: 1000.0,             # 15.4: <1s
    OperationType.CHUNK_LISTING: 500.0,       # 15.5: <500ms
    OperationType.QUERY_CLASSIFICATION: 300.0,
    OperationType.SUMMARIZATION: 5000.0,
    OperationType.COMPARISON: 3000.0,
    OperationType.CHUNK_SEARCH: 500.0,
    OperationType.ANSWER_GENERATION: 3000.0,
    OperationType.TRACE_RECORDING: 100.0,
    OperationType.CACHE_LOOKUP: 50.0,
    OperationType.EXTRACTION: 30000.0,
    OperationType.INDEXING: 60000.0,
}


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class PerformanceThresholds:
    """
    Configurable performance thresholds.
    
    Attributes:
        thresholds: Dictionary mapping operation types to threshold in ms.
        warning_multiplier: Multiplier for warning threshold (default 0.8).
    """
    thresholds: dict[OperationType, float] = field(
        default_factory=lambda: DEFAULT_THRESHOLDS.copy()
    )
    warning_multiplier: float = 0.8
    
    def get_threshold(self, operation: OperationType) -> float:
        """Get threshold for an operation type."""
        return self.thresholds.get(operation, 1000.0)
    
    def get_warning_threshold(self, operation: OperationType) -> float:
        """Get warning threshold (before hard limit)."""
        return self.get_threshold(operation) * self.warning_multiplier
    
    def set_threshold(self, operation: OperationType, threshold_ms: float) -> None:
        """Set threshold for an operation type."""
        if threshold_ms <= 0:
            raise ValueError(f"Threshold must be positive, got {threshold_ms}")
        self.thresholds[operation] = threshold_ms


@dataclass
class PerformanceRecord:
    """
    Record of a single performance measurement.
    
    Attributes:
        operation: Type of operation performed.
        duration_ms: Duration in milliseconds.
        threshold_ms: Threshold for this operation.
        exceeded_threshold: Whether threshold was exceeded.
        timestamp: When the operation occurred.
        context: Additional context about the operation.
    """
    operation: OperationType
    duration_ms: float
    threshold_ms: float
    exceeded_threshold: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)
    context: dict[str, Any] = field(default_factory=dict)
    
    @property
    def threshold_ratio(self) -> float:
        """Get ratio of duration to threshold."""
        if self.threshold_ms <= 0:
            return 0.0
        return self.duration_ms / self.threshold_ms


@dataclass
class PerformanceSummary:
    """
    Summary of performance metrics for an operation type.
    
    Attributes:
        operation: Type of operation.
        count: Number of measurements.
        total_ms: Total time in milliseconds.
        min_ms: Minimum duration.
        max_ms: Maximum duration.
        avg_ms: Average duration.
        threshold_ms: Configured threshold.
        exceeded_count: Number of threshold exceedances.
        exceeded_percent: Percentage of exceedances.
    """
    operation: OperationType
    count: int
    total_ms: float
    min_ms: float
    max_ms: float
    avg_ms: float
    threshold_ms: float
    exceeded_count: int
    exceeded_percent: float
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation": self.operation.value,
            "count": self.count,
            "total_ms": round(self.total_ms, 2),
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "avg_ms": round(self.avg_ms, 2),
            "threshold_ms": self.threshold_ms,
            "exceeded_count": self.exceeded_count,
            "exceeded_percent": round(self.exceeded_percent, 2)
        }


# =============================================================================
# Performance Monitor Service
# =============================================================================

class PerformanceMonitor:
    """
    Monitors and logs performance metrics for pipeline operations.
    
    Tracks timing for various operations, logs warnings when thresholds
    are exceeded, and provides summary statistics. Thread-safe for
    concurrent access.
    
    All dependencies are injected via constructor following DIP.
    
    Attributes:
        _thresholds: Configured performance thresholds.
        _metrics_collector: Metrics collection service.
        _records: List of performance records (bounded).
        _lock: Thread lock for concurrent access.
    
    Example:
        >>> monitor = PerformanceMonitor()
        >>> with monitor.measure(OperationType.FILE_SELECTION):
        ...     result = select_files(query)
        >>> summary = monitor.get_summary(OperationType.FILE_SELECTION)
    
    Supports Requirements 15.1-15.6.
    """
    
    # Maximum records to keep in memory
    MAX_RECORDS = 10000
    
    def __init__(
        self,
        thresholds: Optional[PerformanceThresholds] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        max_records: int = MAX_RECORDS
    ) -> None:
        """
        Initialize the performance monitor.
        
        Args:
            thresholds: Performance thresholds configuration.
            metrics_collector: Metrics collection service.
            max_records: Maximum records to keep in memory.
        """
        self._thresholds = thresholds or PerformanceThresholds()
        self._metrics_collector = metrics_collector or get_metrics_collector()
        self._max_records = max_records
        self._records: list[PerformanceRecord] = []
        self._lock = threading.Lock()
        self._logger = logging.getLogger(__name__)
    
    @contextmanager
    def measure(
        self,
        operation: OperationType,
        context: Optional[dict[str, Any]] = None
    ):
        """
        Context manager for measuring operation duration.
        
        Measures the duration of the wrapped code block and records
        the result. Logs warnings if thresholds are exceeded.
        
        Args:
            operation: Type of operation being measured.
            context: Additional context for the measurement.
        
        Yields:
            None
        
        Example:
            >>> with monitor.measure(OperationType.FILE_SELECTION):
            ...     files = select_files(query)
        
        Supports Requirement 15.6: Log warnings when thresholds exceeded.
        """
        start_time = time.perf_counter()
        
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._record_measurement(operation, duration_ms, context or {})
    
    def record(
        self,
        operation: OperationType,
        duration_ms: float,
        context: Optional[dict[str, Any]] = None
    ) -> PerformanceRecord:
        """
        Record a performance measurement directly.
        
        Args:
            operation: Type of operation.
            duration_ms: Duration in milliseconds.
            context: Additional context.
            
        Returns:
            The created PerformanceRecord.
        """
        return self._record_measurement(operation, duration_ms, context or {})
    
    def _record_measurement(
        self,
        operation: OperationType,
        duration_ms: float,
        context: dict[str, Any]
    ) -> PerformanceRecord:
        """
        Record a measurement and check thresholds.
        
        Args:
            operation: Type of operation.
            duration_ms: Duration in milliseconds.
            context: Additional context.
            
        Returns:
            The created PerformanceRecord.
        """
        threshold_ms = self._thresholds.get_threshold(operation)
        exceeded = duration_ms > threshold_ms
        
        record = PerformanceRecord(
            operation=operation,
            duration_ms=duration_ms,
            threshold_ms=threshold_ms,
            exceeded_threshold=exceeded,
            context=context
        )
        
        # Store record (thread-safe)
        with self._lock:
            self._records.append(record)
            
            # Trim if exceeding max
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]
        
        # Record in metrics collector
        self._metrics_collector.record_timer(
            f"pipeline_{operation.value}_duration",
            duration_ms,
            labels={"operation": operation.value}
        )
        
        # Log based on threshold
        if exceeded:
            self._log_threshold_exceeded(record)
        elif duration_ms > self._thresholds.get_warning_threshold(operation):
            self._log_threshold_warning(record)
        else:
            self._logger.debug(
                f"{operation.value} completed in {duration_ms:.2f}ms "
                f"(threshold: {threshold_ms:.2f}ms)"
            )
        
        return record
    
    def _log_threshold_exceeded(self, record: PerformanceRecord) -> None:
        """
        Log warning for threshold exceedance.
        
        Supports Requirement 15.6: Log warnings when thresholds exceeded.
        """
        context_str = ", ".join(f"{k}={v}" for k, v in record.context.items())
        
        self._logger.warning(
            f"PERFORMANCE THRESHOLD EXCEEDED: {record.operation.value} "
            f"took {record.duration_ms:.2f}ms "
            f"(threshold: {record.threshold_ms:.2f}ms, "
            f"ratio: {record.threshold_ratio:.2f}x)"
            + (f" [{context_str}]" if context_str else "")
        )
    
    def _log_threshold_warning(self, record: PerformanceRecord) -> None:
        """Log warning for approaching threshold."""
        self._logger.info(
            f"Performance warning: {record.operation.value} "
            f"took {record.duration_ms:.2f}ms "
            f"(approaching threshold: {record.threshold_ms:.2f}ms)"
        )
    
    def get_summary(
        self,
        operation: Optional[OperationType] = None
    ) -> list[PerformanceSummary]:
        """
        Get performance summary for operations.
        
        Args:
            operation: Specific operation to summarize, or None for all.
            
        Returns:
            List of PerformanceSummary objects.
        """
        with self._lock:
            records = list(self._records)
        
        # Group by operation
        by_operation: dict[OperationType, list[PerformanceRecord]] = {}
        for record in records:
            if operation and record.operation != operation:
                continue
            if record.operation not in by_operation:
                by_operation[record.operation] = []
            by_operation[record.operation].append(record)
        
        # Calculate summaries
        summaries: list[PerformanceSummary] = []
        for op, op_records in by_operation.items():
            if not op_records:
                continue
            
            durations = [r.duration_ms for r in op_records]
            exceeded = sum(1 for r in op_records if r.exceeded_threshold)
            
            summaries.append(PerformanceSummary(
                operation=op,
                count=len(op_records),
                total_ms=sum(durations),
                min_ms=min(durations),
                max_ms=max(durations),
                avg_ms=sum(durations) / len(durations),
                threshold_ms=self._thresholds.get_threshold(op),
                exceeded_count=exceeded,
                exceeded_percent=(exceeded / len(op_records)) * 100
            ))
        
        return summaries
    
    def get_recent_records(
        self,
        operation: Optional[OperationType] = None,
        limit: int = 100
    ) -> list[PerformanceRecord]:
        """
        Get recent performance records.
        
        Args:
            operation: Filter by operation type.
            limit: Maximum records to return.
            
        Returns:
            List of recent PerformanceRecord objects.
        """
        with self._lock:
            records = list(self._records)
        
        if operation:
            records = [r for r in records if r.operation == operation]
        
        return records[-limit:]
    
    def get_exceeded_records(
        self,
        limit: int = 100
    ) -> list[PerformanceRecord]:
        """
        Get records that exceeded thresholds.
        
        Args:
            limit: Maximum records to return.
            
        Returns:
            List of PerformanceRecord objects that exceeded thresholds.
        """
        with self._lock:
            records = [r for r in self._records if r.exceeded_threshold]
        
        return records[-limit:]
    
    def clear_records(self) -> None:
        """Clear all stored records."""
        with self._lock:
            self._records.clear()
    
    def update_threshold(
        self,
        operation: OperationType,
        threshold_ms: float
    ) -> None:
        """
        Update threshold for an operation.
        
        Args:
            operation: Operation type to update.
            threshold_ms: New threshold in milliseconds.
        """
        self._thresholds.set_threshold(operation, threshold_ms)
        self._logger.info(
            f"Updated threshold for {operation.value}: {threshold_ms}ms"
        )


# =============================================================================
# Timing Decorator
# =============================================================================

def timed(
    operation: OperationType,
    monitor: Optional[PerformanceMonitor] = None
) -> Callable[[F], F]:
    """
    Decorator for timing function execution.
    
    Wraps a function to measure its execution time and record it
    in the performance monitor.
    
    Args:
        operation: Type of operation being timed.
        monitor: Performance monitor to use. Uses global if not provided.
        
    Returns:
        Decorated function.
    
    Example:
        >>> @timed(OperationType.FILE_SELECTION)
        ... def select_files(query: str) -> list[str]:
        ...     return ["file1.xlsx", "file2.xlsx"]
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            perf_monitor = monitor or _get_global_monitor()
            
            with perf_monitor.measure(
                operation,
                context={"function": func.__name__}
            ):
                return func(*args, **kwargs)
        
        return wrapper  # type: ignore
    
    return decorator


def timed_async(
    operation: OperationType,
    monitor: Optional[PerformanceMonitor] = None
) -> Callable[[F], F]:
    """
    Decorator for timing async function execution.
    
    Args:
        operation: Type of operation being timed.
        monitor: Performance monitor to use.
        
    Returns:
        Decorated async function.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            perf_monitor = monitor or _get_global_monitor()
            start_time = time.perf_counter()
            
            try:
                return await func(*args, **kwargs)
            finally:
                duration_ms = (time.perf_counter() - start_time) * 1000
                perf_monitor.record(
                    operation,
                    duration_ms,
                    context={"function": func.__name__}
                )
        
        return wrapper  # type: ignore
    
    return decorator


# =============================================================================
# Global Monitor Instance
# =============================================================================

_global_monitor: Optional[PerformanceMonitor] = None
_global_lock = threading.Lock()


def _get_global_monitor() -> PerformanceMonitor:
    """Get or create global performance monitor."""
    global _global_monitor
    
    with _global_lock:
        if _global_monitor is None:
            _global_monitor = PerformanceMonitor()
        return _global_monitor


def get_performance_monitor() -> PerformanceMonitor:
    """
    Get the global performance monitor instance.
    
    Returns:
        Global PerformanceMonitor instance.
    """
    return _get_global_monitor()


def reset_performance_monitor() -> None:
    """Reset the global performance monitor."""
    global _global_monitor
    
    with _global_lock:
        if _global_monitor:
            _global_monitor.clear_records()
        _global_monitor = None


# =============================================================================
# Convenience Functions
# =============================================================================

def measure_operation(
    operation: OperationType,
    context: Optional[dict[str, Any]] = None
):
    """
    Context manager for measuring operation duration.
    
    Convenience function using the global monitor.
    
    Args:
        operation: Type of operation.
        context: Additional context.
        
    Returns:
        Context manager for measurement.
    
    Example:
        >>> with measure_operation(OperationType.FILE_SELECTION):
        ...     files = select_files(query)
    """
    return get_performance_monitor().measure(operation, context)


def record_operation(
    operation: OperationType,
    duration_ms: float,
    context: Optional[dict[str, Any]] = None
) -> PerformanceRecord:
    """
    Record an operation duration directly.
    
    Args:
        operation: Type of operation.
        duration_ms: Duration in milliseconds.
        context: Additional context.
        
    Returns:
        The created PerformanceRecord.
    """
    return get_performance_monitor().record(operation, duration_ms, context)


def get_performance_summary(
    operation: Optional[OperationType] = None
) -> list[PerformanceSummary]:
    """
    Get performance summary.
    
    Args:
        operation: Specific operation or None for all.
        
    Returns:
        List of PerformanceSummary objects.
    """
    return get_performance_monitor().get_summary(operation)
