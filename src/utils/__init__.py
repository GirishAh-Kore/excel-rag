"""
Utility modules for the RAG system.

This module provides utility functions and services including:
- Logging configuration
- Metrics collection
- Performance monitoring
- Dependency checking
"""

from src.utils.logging_config import (
    get_logger,
    init_logging,
    log_with_context,
    setup_logger,
)
from src.utils.metrics import (
    MetricsCollector,
    Timer,
    get_metrics_collector,
    increment_counter,
    record_histogram,
    record_timer,
    reset_metrics,
    set_gauge,
    timer,
)
from src.utils.performance_monitor import (
    OperationType,
    PerformanceMonitor,
    PerformanceRecord,
    PerformanceSummary,
    PerformanceThresholds,
    get_performance_monitor,
    get_performance_summary,
    measure_operation,
    record_operation,
    reset_performance_monitor,
    timed,
    timed_async,
)

__all__ = [
    # Logging
    "get_logger",
    "init_logging",
    "log_with_context",
    "setup_logger",
    # Metrics
    "MetricsCollector",
    "Timer",
    "get_metrics_collector",
    "increment_counter",
    "record_histogram",
    "record_timer",
    "reset_metrics",
    "set_gauge",
    "timer",
    # Performance monitoring
    "OperationType",
    "PerformanceMonitor",
    "PerformanceRecord",
    "PerformanceSummary",
    "PerformanceThresholds",
    "get_performance_monitor",
    "get_performance_summary",
    "measure_operation",
    "record_operation",
    "reset_performance_monitor",
    "timed",
    "timed_async",
]
