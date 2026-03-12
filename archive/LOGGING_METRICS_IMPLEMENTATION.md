# Logging and Metrics Implementation

This document describes the logging and metrics implementation for the Google Drive Excel RAG system.

## Overview

The system includes comprehensive logging and metrics collection to support monitoring, debugging, and performance analysis.

### Features

1. **Structured Logging**
   - JSON format for production
   - Human-readable format for development
   - Correlation IDs for request tracing
   - Component-specific log files
   - Log rotation (daily, 30-day retention)

2. **Performance Metrics**
   - Counters (cumulative values)
   - Gauges (current values)
   - Histograms (distributions)
   - Timers (duration tracking)
   - System metrics (CPU, memory)

3. **Metrics Export**
   - Prometheus format for monitoring tools
   - JSON format for dashboards
   - Real-time metrics via API

## Structured Logging

### Configuration

Logging is configured in `src/utils/logging_config.py`:

```python
from src.utils.logging_config import get_logger, init_logging

# Initialize logging system
init_logging()

# Get a logger for your module
logger = get_logger(__name__)
```

### Log Levels

- **DEBUG**: Detailed information for debugging
- **INFO**: General informational messages
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical errors requiring immediate attention

### Log Files

Logs are written to the `logs/` directory:

- `logs/api.log` - API requests and responses
- `logs/indexing.log` - Indexing operations
- `logs/queries.log` - Query processing
- `logs/errors.log` - All errors (ERROR level and above)

### Usage Examples

```python
from src.utils.logging_config import get_logger, log_with_context

logger = get_logger(__name__)

# Basic logging
logger.info("Processing started")
logger.warning("Low confidence result")
logger.error("Failed to process file", exc_info=True)

# Logging with context
log_with_context(
    logger,
    "info",
    "File processed successfully",
    file_name="expenses.xlsx",
    sheets=3,
    duration_ms=1250
)
```

### Correlation IDs

Every API request automatically gets a correlation ID that's included in all log entries:

```python
from src.api.middleware import get_correlation_id

correlation_id = get_correlation_id()
logger.info(f"Processing request", extra={'correlation_id': correlation_id})
```

Correlation IDs are:
- Generated automatically for each request
- Included in response headers (`X-Correlation-ID`)
- Propagated through all components
- Useful for tracing requests across logs

## Performance Metrics

### Metrics Collector

The metrics collector is available globally:

```python
from src.utils.metrics import (
    increment_counter,
    set_gauge,
    record_histogram,
    timer
)
```

### Metric Types

#### 1. Counters

Cumulative values that only increase:

```python
# Increment by 1
increment_counter('indexing.files_processed')

# Increment by specific value
increment_counter('indexing.sheets_processed', value=5)

# Counter with labels
increment_counter('query.requests', labels={'type': 'comparison'})
```

#### 2. Gauges

Current values that can go up or down:

```python
# Set current value
set_gauge('indexing.total_files', 100)
set_gauge('indexing.throughput_files_per_minute', 12.5)
set_gauge('query.active_sessions', 5)
```

#### 3. Histograms

Track distributions of values:

```python
# Record values
record_histogram('query.confidence_score', 0.85)
record_histogram('indexing.file_size_mb', 2.5)

# Get statistics
from src.utils.metrics import get_metrics_collector

collector = get_metrics_collector()
stats = collector.get_histogram_stats('query.confidence_score')

print(f"P50: {stats.p50}")
print(f"P95: {stats.p95}")
print(f"P99: {stats.p99}")
```

#### 4. Timers

Track operation durations:

```python
# Using context manager
with timer('indexing.extract_workbook'):
    # Your code here
    extract_workbook(file_content)

# Manual timing
from src.utils.metrics import record_timer
import time

start = time.time()
# Your code here
duration_ms = (time.time() - start) * 1000
record_timer('query.response_time', duration_ms)
```

### Built-in Metrics

#### Indexing Metrics

- `indexing.full_index_started` - Counter
- `indexing.full_index_completed` - Counter
- `indexing.full_index_failed` - Counter
- `indexing.incremental_index_started` - Counter
- `indexing.incremental_index_completed` - Counter
- `indexing.files_processed` - Counter
- `indexing.files_failed` - Counter
- `indexing.sheets_processed` - Counter
- `indexing.total_files` - Gauge
- `indexing.throughput_files_per_minute` - Gauge
- `indexing.file_processing_time` - Timer
- `indexing.download_file` - Timer
- `indexing.extract_workbook` - Timer

#### Query Metrics

- `query.total_queries` - Counter
- `query.successful_queries` - Counter
- `query.failed_queries` - Counter
- `query.comparison_queries` - Counter
- `query.clarifications_needed` - Counter
- `query.new_sessions` - Counter
- `query.response_time` - Timer
- `query.analyze` - Timer
- `query.semantic_search` - Timer

#### System Metrics

- `process_cpu_percent` - Gauge
- `process_memory_mb` - Gauge
- `process_uptime_seconds` - Gauge

## Metrics API

### Prometheus Format

Get metrics in Prometheus exposition format:

```bash
GET /api/v1/metrics
```

Response:
```
# TYPE indexing_files_processed counter
indexing_files_processed 150

# TYPE query_response_time_seconds histogram
query_response_time_seconds_count 50
query_response_time_seconds_sum 2.5
query_response_time_seconds_bucket{le="0.5"} 0.08
query_response_time_seconds_bucket{le="0.95"} 0.12
```

### JSON Format (Dashboard)

Get metrics in JSON format for dashboards:

```bash
GET /api/v1/metrics/dashboard
```

Response:
```json
{
  "counters": {
    "indexing.files_processed": 150,
    "query.total_queries": 50
  },
  "gauges": {
    "indexing.throughput_files_per_minute": 12.5
  },
  "timers": {
    "query.response_time": {
      "count": 50,
      "p50_ms": 80,
      "p95_ms": 120,
      "p99_ms": 150
    }
  },
  "system": {
    "cpu_percent": 15.2,
    "memory_mb": 256.5
  },
  "uptime_seconds": 3600
}
```

## Integration with Components

### Indexing Pipeline

The `IndexingOrchestrator` automatically tracks:
- Files processed/failed
- Processing throughput
- Download and extraction times
- Memory usage during indexing

```python
from src.indexing.indexing_orchestrator import IndexingOrchestrator

orchestrator = IndexingOrchestrator(...)
report = orchestrator.full_index()

# Metrics are automatically tracked:
# - indexing.files_processed
# - indexing.throughput_files_per_minute
# - indexing.file_processing_time
```

### Query Engine

The `QueryEngine` automatically tracks:
- Query counts and success rates
- Response times (p50, p95, p99)
- Clarification rates
- Component-level timings

```python
from src.query.query_engine import QueryEngine

engine = QueryEngine(...)
result = engine.process_query("What is the total expense?")

# Metrics are automatically tracked:
# - query.total_queries
# - query.response_time
# - query.analyze
# - query.semantic_search
```

### API Endpoints

All API endpoints automatically track:
- Request counts
- Response times
- Error rates
- Rate limit hits

Middleware adds:
- Correlation IDs
- Request/response logging
- Performance timing

## Monitoring Setup

### Prometheus Integration

1. Configure Prometheus to scrape metrics:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'excel-rag'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/v1/metrics'
    scrape_interval: 15s
```

2. Start Prometheus:

```bash
prometheus --config.file=prometheus.yml
```

### Grafana Dashboard

1. Add Prometheus as data source in Grafana
2. Import dashboard or create custom panels:
   - Query response time (P50, P95, P99)
   - Indexing throughput
   - Error rates
   - System resources

### Example Queries

Prometheus queries for common metrics:

```promql
# Average query response time
rate(query_response_time_seconds_sum[5m]) / rate(query_response_time_seconds_count[5m])

# Indexing throughput
indexing_throughput_files_per_minute

# Error rate
rate(query_failed_queries[5m]) / rate(query_total_queries[5m])

# Memory usage
process_memory_mb
```

## Configuration

### Environment Variables

```bash
# Logging configuration
ENVIRONMENT=production  # or development
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Metrics configuration
METRICS_ENABLED=true
METRICS_HISTORY_SIZE=1000  # Number of values to keep in memory
```

### Log Format

Production (JSON):
```json
{
  "timestamp": "2024-01-15 10:30:45",
  "level": "INFO",
  "logger": "src.indexing.indexing_orchestrator",
  "module": "indexing_orchestrator",
  "function": "full_index",
  "line": 125,
  "correlation_id": "abc-123-def",
  "message": "Processing file",
  "file_name": "expenses.xlsx",
  "sheets": 3
}
```

Development (Human-readable):
```
2024-01-15 10:30:45 - src.indexing.indexing_orchestrator - INFO - [abc-123-def] - Processing file
```

## Best Practices

### Logging

1. **Use appropriate log levels**
   - DEBUG: Detailed debugging information
   - INFO: Normal operations
   - WARNING: Potential issues
   - ERROR: Failures that need attention

2. **Include context**
   - Use `log_with_context()` for structured data
   - Include relevant IDs (file_id, session_id)
   - Add timing information when relevant

3. **Avoid sensitive data**
   - Don't log passwords or tokens
   - Sanitize user input
   - Use placeholders for PII

### Metrics

1. **Choose the right metric type**
   - Counters: Total requests, errors
   - Gauges: Current connections, queue size
   - Histograms: Response times, file sizes
   - Timers: Operation durations

2. **Use labels wisely**
   - Keep cardinality low
   - Use for categorization (type, status)
   - Avoid high-cardinality values (user IDs)

3. **Monitor key metrics**
   - Response times (P50, P95, P99)
   - Error rates
   - Throughput
   - Resource usage

## Troubleshooting

### High Memory Usage

Check metrics:
```python
from src.utils.metrics import get_metrics_collector

collector = get_metrics_collector()
metrics = collector.get_all_metrics()
print(f"Memory: {metrics['system']['memory_mb']} MB")
```

### Slow Queries

Check timer statistics:
```python
stats = collector.get_timer_stats('query.response_time')
print(f"P95: {stats.p95} ms")
print(f"P99: {stats.p99} ms")
```

### Log File Growth

Logs rotate daily and keep 30 days by default. To change:

```python
# In src/utils/logging_config.py
file_handler = logging.handlers.TimedRotatingFileHandler(
    filename=file_path,
    when='midnight',
    interval=1,
    backupCount=30,  # Change this value
    encoding='utf-8'
)
```

## Example Usage

See `examples/logging_metrics_usage.py` for complete examples:

```bash
python examples/logging_metrics_usage.py
```

This demonstrates:
- Structured logging
- Metrics collection
- Export formats
- Real-world usage patterns

## Summary

The logging and metrics system provides:

✅ **Structured logging** with JSON format and correlation IDs
✅ **Performance metrics** with counters, gauges, histograms, and timers
✅ **Prometheus integration** for monitoring tools
✅ **Component integration** in indexing and query pipelines
✅ **API endpoints** for metrics access
✅ **Best practices** for production monitoring

This enables comprehensive observability for debugging, performance analysis, and production monitoring.
