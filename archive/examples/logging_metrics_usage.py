"""
Example: Logging and Metrics Usage

This example demonstrates how to use the structured logging and metrics
collection features in the Google Drive Excel RAG system.
"""

import time
from src.utils.logging_config import get_logger, log_with_context, init_logging
from src.utils.metrics import (
    get_metrics_collector,
    increment_counter,
    set_gauge,
    record_histogram,
    timer,
    reset_metrics
)


def example_structured_logging():
    """Demonstrate structured logging features"""
    print("\n=== Structured Logging Example ===\n")
    
    # Initialize logging
    init_logging()
    
    # Get a logger for this module
    logger = get_logger(__name__)
    
    # Basic logging
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Logging with extra context
    log_with_context(
        logger,
        "info",
        "Processing file",
        file_name="expenses_2024.xlsx",
        file_size=1024000,
        sheet_count=3
    )
    
    # Logging with correlation ID (simulated)
    from src.api.middleware import correlation_id_var
    correlation_id_var.set("test-correlation-id-123")
    
    logger.info("This log will include the correlation ID")
    
    print("✓ Structured logging examples completed")
    print("  Check logs/ directory for log files:")
    print("  - logs/api.log")
    print("  - logs/indexing.log")
    print("  - logs/queries.log")
    print("  - logs/errors.log")


def example_metrics_collection():
    """Demonstrate metrics collection features"""
    print("\n=== Metrics Collection Example ===\n")
    
    # Reset metrics for clean example
    reset_metrics()
    
    # Get metrics collector
    collector = get_metrics_collector()
    
    # 1. Counter metrics
    print("1. Counter Metrics:")
    increment_counter('example.requests_total')
    increment_counter('example.requests_total')
    increment_counter('example.requests_total', value=3)
    print(f"   Total requests: {collector.get_counter('example.requests_total')}")
    
    # Counter with labels
    increment_counter('example.requests_by_type', labels={'type': 'query'})
    increment_counter('example.requests_by_type', labels={'type': 'query'})
    increment_counter('example.requests_by_type', labels={'type': 'index'})
    print(f"   Query requests: {collector.get_counter('example.requests_by_type', labels={'type': 'query'})}")
    print(f"   Index requests: {collector.get_counter('example.requests_by_type', labels={'type': 'index'})}")
    
    # 2. Gauge metrics
    print("\n2. Gauge Metrics:")
    set_gauge('example.active_connections', 10)
    set_gauge('example.memory_usage_mb', 256.5)
    print(f"   Active connections: {collector.get_gauge('example.active_connections')}")
    print(f"   Memory usage: {collector.get_gauge('example.memory_usage_mb')} MB")
    
    # 3. Histogram metrics
    print("\n3. Histogram Metrics:")
    for value in [10, 20, 15, 30, 25, 18, 22, 28, 12, 35]:
        record_histogram('example.request_size_kb', value)
    
    stats = collector.get_histogram_stats('example.request_size_kb')
    if stats:
        print(f"   Request size statistics:")
        print(f"   - Count: {stats.count}")
        print(f"   - Min: {stats.min} KB")
        print(f"   - Max: {stats.max} KB")
        print(f"   - Mean: {stats.mean:.2f} KB")
        print(f"   - P50: {stats.p50:.2f} KB")
        print(f"   - P95: {stats.p95:.2f} KB")
        print(f"   - P99: {stats.p99:.2f} KB")
    
    # 4. Timer metrics
    print("\n4. Timer Metrics:")
    
    # Using timer context manager
    with timer('example.operation_duration'):
        time.sleep(0.1)  # Simulate operation
    
    with timer('example.operation_duration'):
        time.sleep(0.15)  # Simulate another operation
    
    with timer('example.operation_duration'):
        time.sleep(0.12)  # Simulate another operation
    
    timer_stats = collector.get_timer_stats('example.operation_duration')
    if timer_stats:
        print(f"   Operation duration statistics:")
        print(f"   - Count: {timer_stats.count}")
        print(f"   - Min: {timer_stats.min:.2f} ms")
        print(f"   - Max: {timer_stats.max:.2f} ms")
        print(f"   - Mean: {timer_stats.mean:.2f} ms")
        print(f"   - P50: {timer_stats.p50:.2f} ms")
        print(f"   - P95: {timer_stats.p95:.2f} ms")
    
    print("\n✓ Metrics collection examples completed")


def example_metrics_export():
    """Demonstrate metrics export formats"""
    print("\n=== Metrics Export Example ===\n")
    
    collector = get_metrics_collector()
    
    # 1. JSON format (for dashboard)
    print("1. JSON Format (Dashboard):")
    all_metrics = collector.get_all_metrics()
    print(f"   Counters: {len(all_metrics['counters'])} metrics")
    print(f"   Gauges: {len(all_metrics['gauges'])} metrics")
    print(f"   Histograms: {len(all_metrics['histograms'])} metrics")
    print(f"   Timers: {len(all_metrics['timers'])} metrics")
    print(f"   System CPU: {all_metrics['system']['cpu_percent']:.2f}%")
    print(f"   System Memory: {all_metrics['system']['memory_mb']:.2f} MB")
    print(f"   Uptime: {all_metrics['uptime_seconds']:.2f} seconds")
    
    # 2. Prometheus format
    print("\n2. Prometheus Format:")
    prometheus_text = collector.to_prometheus_format()
    print("   First 500 characters of Prometheus export:")
    print(f"   {prometheus_text[:500]}...")
    
    print("\n✓ Metrics export examples completed")


def example_real_world_usage():
    """Demonstrate real-world usage in indexing and query scenarios"""
    print("\n=== Real-World Usage Example ===\n")
    
    logger = get_logger(__name__)
    
    # Simulate indexing workflow
    print("1. Simulating Indexing Workflow:")
    
    increment_counter('indexing.full_index_started')
    set_gauge('indexing.total_files', 10)
    
    for i in range(10):
        with timer('indexing.file_processing_time'):
            # Simulate file processing
            time.sleep(0.05)
            
            # Track download time
            with timer('indexing.download_file'):
                time.sleep(0.01)
            
            # Track extraction time
            with timer('indexing.extract_workbook'):
                time.sleep(0.02)
            
            increment_counter('indexing.files_processed')
            increment_counter('indexing.sheets_processed', value=3)
            
            log_with_context(
                logger,
                "info",
                f"Processed file {i+1}/10",
                file_number=i+1,
                sheets=3
            )
    
    increment_counter('indexing.full_index_completed')
    
    # Calculate throughput
    collector = get_metrics_collector()
    timer_stats = collector.get_timer_stats('indexing.file_processing_time')
    if timer_stats:
        avg_time_seconds = timer_stats.mean / 1000
        throughput = 60 / avg_time_seconds if avg_time_seconds > 0 else 0
        set_gauge('indexing.throughput_files_per_minute', throughput)
        print(f"   Average file processing time: {timer_stats.mean:.2f} ms")
        print(f"   Throughput: {throughput:.2f} files/minute")
    
    # Simulate query workflow
    print("\n2. Simulating Query Workflow:")
    
    for i in range(5):
        increment_counter('query.total_queries')
        
        with timer('query.response_time'):
            # Simulate query analysis
            with timer('query.analyze'):
                time.sleep(0.02)
            
            # Simulate semantic search
            with timer('query.semantic_search'):
                time.sleep(0.03)
            
            # Simulate answer generation
            with timer('query.generate_answer'):
                time.sleep(0.04)
            
            increment_counter('query.successful_queries')
            
            log_with_context(
                logger,
                "info",
                f"Processed query {i+1}",
                query_number=i+1,
                confidence=0.85
            )
    
    # Show query statistics
    query_stats = collector.get_timer_stats('query.response_time')
    if query_stats:
        print(f"   Query response time statistics:")
        print(f"   - P50: {query_stats.p50:.2f} ms")
        print(f"   - P95: {query_stats.p95:.2f} ms")
        print(f"   - P99: {query_stats.p99:.2f} ms")
    
    print("\n✓ Real-world usage examples completed")


def main():
    """Run all examples"""
    print("=" * 60)
    print("Logging and Metrics Usage Examples")
    print("=" * 60)
    
    example_structured_logging()
    example_metrics_collection()
    example_metrics_export()
    example_real_world_usage()
    
    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Check logs/ directory for structured log files")
    print("2. Access metrics via API:")
    print("   - GET /api/v1/metrics (Prometheus format)")
    print("   - GET /api/v1/metrics/dashboard (JSON format)")
    print("3. Integrate with monitoring tools (Prometheus, Grafana)")


if __name__ == "__main__":
    main()
