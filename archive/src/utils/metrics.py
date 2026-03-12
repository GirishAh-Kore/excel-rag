"""Performance metrics collection and monitoring"""

import time
import psutil
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime
import statistics


@dataclass
class MetricValue:
    """Single metric value with timestamp"""
    value: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class HistogramStats:
    """Statistics for histogram metrics"""
    count: int
    sum: float
    min: float
    max: float
    p50: float
    p95: float
    p99: float
    mean: float


class MetricsCollector:
    """Collects and aggregates performance metrics"""
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize metrics collector
        
        Args:
            max_history: Maximum number of values to keep in history
        """
        self.max_history = max_history
        self._lock = threading.Lock()
        
        # Counters: {metric_name: count}
        self._counters: Dict[str, float] = defaultdict(float)
        
        # Gauges: {metric_name: current_value}
        self._gauges: Dict[str, float] = {}
        
        # Histograms: {metric_name: deque of values}
        self._histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        
        # Timers: {metric_name: list of durations}
        self._timers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        
        # Start time for uptime calculation
        self._start_time = time.time()
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """
        Increment a counter metric
        
        Args:
            name: Metric name
            value: Value to add (default 1.0)
            labels: Optional labels for the metric
        """
        with self._lock:
            metric_key = self._make_key(name, labels)
            self._counters[metric_key] += value
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Set a gauge metric to a specific value
        
        Args:
            name: Metric name
            value: Current value
            labels: Optional labels for the metric
        """
        with self._lock:
            metric_key = self._make_key(name, labels)
            self._gauges[metric_key] = value
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Record a value in a histogram
        
        Args:
            name: Metric name
            value: Value to record
            labels: Optional labels for the metric
        """
        with self._lock:
            metric_key = self._make_key(name, labels)
            self._histograms[metric_key].append(value)
    
    def record_timer(self, name: str, duration_ms: float, labels: Optional[Dict[str, str]] = None):
        """
        Record a timer duration
        
        Args:
            name: Metric name
            duration_ms: Duration in milliseconds
            labels: Optional labels for the metric
        """
        with self._lock:
            metric_key = self._make_key(name, labels)
            self._timers[metric_key].append(duration_ms)
    
    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value"""
        with self._lock:
            metric_key = self._make_key(name, labels)
            return self._counters.get(metric_key, 0.0)
    
    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get current gauge value"""
        with self._lock:
            metric_key = self._make_key(name, labels)
            return self._gauges.get(metric_key)
    
    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[HistogramStats]:
        """Get histogram statistics"""
        with self._lock:
            metric_key = self._make_key(name, labels)
            values = list(self._histograms.get(metric_key, []))
            
            if not values:
                return None
            
            sorted_values = sorted(values)
            count = len(sorted_values)
            
            return HistogramStats(
                count=count,
                sum=sum(sorted_values),
                min=sorted_values[0],
                max=sorted_values[-1],
                p50=self._percentile(sorted_values, 50),
                p95=self._percentile(sorted_values, 95),
                p99=self._percentile(sorted_values, 99),
                mean=statistics.mean(sorted_values)
            )
    
    def get_timer_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[HistogramStats]:
        """Get timer statistics"""
        with self._lock:
            metric_key = self._make_key(name, labels)
            values = list(self._timers.get(metric_key, []))
            
            if not values:
                return None
            
            sorted_values = sorted(values)
            count = len(sorted_values)
            
            return HistogramStats(
                count=count,
                sum=sum(sorted_values),
                min=sorted_values[0],
                max=sorted_values[-1],
                p50=self._percentile(sorted_values, 50),
                p95=self._percentile(sorted_values, 95),
                p99=self._percentile(sorted_values, 99),
                mean=statistics.mean(sorted_values)
            )
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics in a structured format"""
        with self._lock:
            metrics = {
                'counters': dict(self._counters),
                'gauges': dict(self._gauges),
                'histograms': {},
                'timers': {},
                'system': self._get_system_metrics(),
                'uptime_seconds': time.time() - self._start_time
            }
            
            # Add histogram stats
            for name in self._histograms.keys():
                stats = self.get_histogram_stats(name.split('{')[0], self._parse_labels(name))
                if stats:
                    metrics['histograms'][name] = {
                        'count': stats.count,
                        'sum': stats.sum,
                        'min': stats.min,
                        'max': stats.max,
                        'p50': stats.p50,
                        'p95': stats.p95,
                        'p99': stats.p99,
                        'mean': stats.mean
                    }
            
            # Add timer stats
            for name in self._timers.keys():
                stats = self.get_timer_stats(name.split('{')[0], self._parse_labels(name))
                if stats:
                    metrics['timers'][name] = {
                        'count': stats.count,
                        'sum_ms': stats.sum,
                        'min_ms': stats.min,
                        'max_ms': stats.max,
                        'p50_ms': stats.p50,
                        'p95_ms': stats.p95,
                        'p99_ms': stats.p99,
                        'mean_ms': stats.mean
                    }
            
            return metrics
    
    def to_prometheus_format(self) -> str:
        """Export metrics in Prometheus text format"""
        lines = []
        
        # Counters
        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        
        # Gauges
        for name, value in self._gauges.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        
        # Histograms
        for name in self._histograms.keys():
            base_name = name.split('{')[0]
            stats = self.get_histogram_stats(base_name, self._parse_labels(name))
            if stats:
                lines.append(f"# TYPE {base_name} histogram")
                lines.append(f"{base_name}_count {stats.count}")
                lines.append(f"{base_name}_sum {stats.sum}")
                lines.append(f"{base_name}_bucket{{le=\"0.5\"}} {stats.p50}")
                lines.append(f"{base_name}_bucket{{le=\"0.95\"}} {stats.p95}")
                lines.append(f"{base_name}_bucket{{le=\"0.99\"}} {stats.p99}")
                lines.append(f"{base_name}_bucket{{le=\"+Inf\"}} {stats.count}")
        
        # Timers (as histograms)
        for name in self._timers.keys():
            base_name = name.split('{')[0]
            stats = self.get_timer_stats(base_name, self._parse_labels(name))
            if stats:
                lines.append(f"# TYPE {base_name}_seconds histogram")
                lines.append(f"{base_name}_seconds_count {stats.count}")
                lines.append(f"{base_name}_seconds_sum {stats.sum / 1000}")  # Convert to seconds
                lines.append(f"{base_name}_seconds_bucket{{le=\"0.5\"}} {stats.p50 / 1000}")
                lines.append(f"{base_name}_seconds_bucket{{le=\"0.95\"}} {stats.p95 / 1000}")
                lines.append(f"{base_name}_seconds_bucket{{le=\"0.99\"}} {stats.p99 / 1000}")
                lines.append(f"{base_name}_seconds_bucket{{le=\"+Inf\"}} {stats.count}")
        
        # System metrics
        system_metrics = self._get_system_metrics()
        lines.append(f"# TYPE process_cpu_percent gauge")
        lines.append(f"process_cpu_percent {system_metrics['cpu_percent']}")
        lines.append(f"# TYPE process_memory_mb gauge")
        lines.append(f"process_memory_mb {system_metrics['memory_mb']}")
        lines.append(f"# TYPE process_uptime_seconds gauge")
        lines.append(f"process_uptime_seconds {time.time() - self._start_time}")
        
        return '\n'.join(lines)
    
    def reset(self):
        """Reset all metrics"""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()
            self._start_time = time.time()
    
    @staticmethod
    def _make_key(name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create metric key with labels"""
        if not labels:
            return name
        label_str = ','.join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    @staticmethod
    def _parse_labels(key: str) -> Optional[Dict[str, str]]:
        """Parse labels from metric key"""
        if '{' not in key:
            return None
        
        label_str = key.split('{')[1].rstrip('}')
        labels = {}
        for pair in label_str.split(','):
            k, v = pair.split('=')
            labels[k] = v.strip('"')
        return labels
    
    @staticmethod
    def _percentile(sorted_values: List[float], percentile: float) -> float:
        """Calculate percentile from sorted values"""
        if not sorted_values:
            return 0.0
        
        index = (len(sorted_values) - 1) * percentile / 100
        lower = int(index)
        upper = lower + 1
        
        if upper >= len(sorted_values):
            return sorted_values[-1]
        
        weight = index - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
    
    @staticmethod
    def _get_system_metrics() -> Dict[str, float]:
        """Get current system metrics"""
        process = psutil.Process()
        
        return {
            'cpu_percent': process.cpu_percent(interval=0.1),
            'memory_mb': process.memory_info().rss / 1024 / 1024,
            'memory_percent': process.memory_percent(),
            'num_threads': process.num_threads(),
            'num_fds': process.num_fds() if hasattr(process, 'num_fds') else 0
        }


class Timer:
    """Context manager for timing operations"""
    
    def __init__(self, collector: MetricsCollector, name: str, labels: Optional[Dict[str, str]] = None):
        """
        Initialize timer
        
        Args:
            collector: MetricsCollector instance
            name: Metric name
            labels: Optional labels for the metric
        """
        self.collector = collector
        self.name = name
        self.labels = labels
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        self.collector.record_timer(self.name, duration_ms, self.labels)


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def reset_metrics():
    """Reset global metrics collector"""
    global _metrics_collector
    if _metrics_collector:
        _metrics_collector.reset()


# Convenience functions
def increment_counter(name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
    """Increment a counter metric"""
    get_metrics_collector().increment_counter(name, value, labels)


def set_gauge(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Set a gauge metric"""
    get_metrics_collector().set_gauge(name, value, labels)


def record_histogram(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Record a histogram value"""
    get_metrics_collector().record_histogram(name, value, labels)


def record_timer(name: str, duration_ms: float, labels: Optional[Dict[str, str]] = None):
    """Record a timer duration"""
    get_metrics_collector().record_timer(name, duration_ms, labels)


def timer(name: str, labels: Optional[Dict[str, str]] = None) -> Timer:
    """Create a timer context manager"""
    return Timer(get_metrics_collector(), name, labels)
