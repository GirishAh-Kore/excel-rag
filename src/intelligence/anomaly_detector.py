"""
Anomaly Detector for Intelligence Module

Detects anomalies and outliers in Excel data:
- Numeric outliers using IQR and Z-score methods
- Missing values detection
- Duplicate detection
- Inconsistent formatting detection

Supports Requirements 38.1, 38.2, 38.3, 38.4.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from statistics import mean, stdev, median
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    """Type of anomaly detected."""
    NUMERIC_OUTLIER_IQR = "numeric_outlier_iqr"
    NUMERIC_OUTLIER_ZSCORE = "numeric_outlier_zscore"
    MISSING_VALUE = "missing_value"
    DUPLICATE = "duplicate"
    INCONSISTENT_FORMAT = "inconsistent_format"
    INVALID_DATA_TYPE = "invalid_data_type"
    EMPTY_ROW = "empty_row"
    EMPTY_COLUMN = "empty_column"


class AnomalySeverity(str, Enum):
    """Severity level of an anomaly."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnomalyDetectorConfig:
    """
    Configuration for AnomalyDetector.
    
    Attributes:
        iqr_multiplier: Multiplier for IQR outlier detection (default 1.5).
        zscore_threshold: Z-score threshold for outlier detection (default 3.0).
        min_sample_size: Minimum sample size for statistical analysis.
        detect_missing: Whether to detect missing values.
        detect_duplicates: Whether to detect duplicates.
        detect_format_issues: Whether to detect formatting inconsistencies.
    """
    iqr_multiplier: float = 1.5
    zscore_threshold: float = 3.0
    min_sample_size: int = 10
    detect_missing: bool = True
    detect_duplicates: bool = True
    detect_format_issues: bool = True
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.iqr_multiplier <= 0:
            raise ValueError(f"iqr_multiplier must be positive, got {self.iqr_multiplier}")
        if self.zscore_threshold <= 0:
            raise ValueError(f"zscore_threshold must be positive, got {self.zscore_threshold}")
        if self.min_sample_size < 2:
            raise ValueError(f"min_sample_size must be at least 2, got {self.min_sample_size}")


@dataclass
class DetectedAnomaly:
    """
    A detected anomaly in the data.
    
    Attributes:
        anomaly_type: Type of anomaly detected.
        severity: Severity level of the anomaly.
        location: Location of the anomaly (row, column, cell reference).
        value: The anomalous value.
        expected: Expected value or range (if applicable).
        message: Human-readable description of the anomaly.
        metadata: Additional context about the anomaly.
    """
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    location: str
    value: Any
    expected: Optional[str]
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnomalyReport:
    """
    Complete anomaly detection report for a dataset.
    
    Attributes:
        total_rows: Total number of rows analyzed.
        total_columns: Total number of columns analyzed.
        anomalies: List of detected anomalies.
        summary: Summary statistics by anomaly type.
        analyzed_at: Timestamp of analysis.
    """
    total_rows: int
    total_columns: int
    anomalies: list[DetectedAnomaly]
    summary: dict[str, int]
    analyzed_at: datetime = field(default_factory=datetime.now)
    
    @property
    def anomaly_count(self) -> int:
        """Total number of anomalies detected."""
        return len(self.anomalies)
    
    @property
    def has_critical(self) -> bool:
        """Whether any critical anomalies were detected."""
        return any(a.severity == AnomalySeverity.CRITICAL for a in self.anomalies)


class AnomalyDetector:
    """
    Detects anomalies and outliers in Excel data.
    
    Provides statistical outlier detection using IQR and Z-score methods,
    as well as detection of missing values, duplicates, and formatting issues.
    
    All dependencies are injected via constructor following DIP.
    
    Supports Requirements 38.1, 38.2, 38.3, 38.4.
    """
    
    def __init__(self, config: Optional[AnomalyDetectorConfig] = None) -> None:
        """
        Initialize AnomalyDetector with configuration.
        
        Args:
            config: Detector configuration. Uses defaults if not provided.
        """
        self._config = config or AnomalyDetectorConfig()
        logger.info(
            f"AnomalyDetector initialized with IQR multiplier={self._config.iqr_multiplier}, "
            f"Z-score threshold={self._config.zscore_threshold}"
        )
    
    def analyze(
        self,
        data: list[list[Any]],
        column_names: Optional[list[str]] = None,
    ) -> AnomalyReport:
        """
        Analyze a dataset for anomalies.
        
        Args:
            data: 2D list of data (rows x columns).
            column_names: Optional column names for better reporting.
        
        Returns:
            AnomalyReport with all detected anomalies.
        """
        if not data:
            return AnomalyReport(
                total_rows=0,
                total_columns=0,
                anomalies=[],
                summary={},
            )
        
        total_rows = len(data)
        total_columns = max(len(row) for row in data) if data else 0
        
        # Generate column names if not provided
        if not column_names:
            column_names = [self._col_letter(i) for i in range(total_columns)]
        
        anomalies: list[DetectedAnomaly] = []
        
        # Detect anomalies by column
        for col_idx in range(total_columns):
            col_name = column_names[col_idx] if col_idx < len(column_names) else self._col_letter(col_idx)
            col_values = [row[col_idx] if col_idx < len(row) else None for row in data]
            
            # Detect numeric outliers
            anomalies.extend(self._detect_numeric_outliers(col_values, col_name))
            
            # Detect missing values
            if self._config.detect_missing:
                anomalies.extend(self._detect_missing_values(col_values, col_name))
            
            # Detect format inconsistencies
            if self._config.detect_format_issues:
                anomalies.extend(self._detect_format_issues(col_values, col_name))
        
        # Detect duplicates (row-level)
        if self._config.detect_duplicates:
            anomalies.extend(self._detect_duplicates(data, column_names))
        
        # Detect empty rows
        anomalies.extend(self._detect_empty_rows(data))
        
        # Build summary
        summary: dict[str, int] = {}
        for anomaly in anomalies:
            key = anomaly.anomaly_type.value
            summary[key] = summary.get(key, 0) + 1
        
        return AnomalyReport(
            total_rows=total_rows,
            total_columns=total_columns,
            anomalies=anomalies,
            summary=summary,
        )
    
    def detect_outliers_iqr(
        self,
        values: Sequence[float],
        column_name: str = "column",
    ) -> list[DetectedAnomaly]:
        """
        Detect numeric outliers using the IQR method.
        
        Args:
            values: Sequence of numeric values.
            column_name: Name of the column for reporting.
        
        Returns:
            List of detected outlier anomalies.
        """
        numeric_values = self._extract_numeric(values)
        
        if len(numeric_values) < self._config.min_sample_size:
            logger.debug(f"Insufficient data for IQR analysis in {column_name}")
            return []
        
        sorted_values = sorted(numeric_values)
        n = len(sorted_values)
        
        q1_idx = n // 4
        q3_idx = (3 * n) // 4
        
        q1 = sorted_values[q1_idx]
        q3 = sorted_values[q3_idx]
        iqr = q3 - q1
        
        lower_bound = q1 - self._config.iqr_multiplier * iqr
        upper_bound = q3 + self._config.iqr_multiplier * iqr
        
        anomalies: list[DetectedAnomaly] = []
        
        for idx, (orig_idx, value) in enumerate(numeric_values):
            if value < lower_bound or value > upper_bound:
                severity = self._calculate_outlier_severity(value, lower_bound, upper_bound, iqr)
                anomalies.append(DetectedAnomaly(
                    anomaly_type=AnomalyType.NUMERIC_OUTLIER_IQR,
                    severity=severity,
                    location=f"{column_name}[{orig_idx + 1}]",
                    value=value,
                    expected=f"[{lower_bound:.2f}, {upper_bound:.2f}]",
                    message=f"Value {value} is outside IQR bounds",
                    metadata={
                        "q1": q1,
                        "q3": q3,
                        "iqr": iqr,
                        "lower_bound": lower_bound,
                        "upper_bound": upper_bound,
                    },
                ))
        
        return anomalies
    
    def detect_outliers_zscore(
        self,
        values: Sequence[float],
        column_name: str = "column",
    ) -> list[DetectedAnomaly]:
        """
        Detect numeric outliers using the Z-score method.
        
        Args:
            values: Sequence of numeric values.
            column_name: Name of the column for reporting.
        
        Returns:
            List of detected outlier anomalies.
        """
        numeric_values = self._extract_numeric(values)
        
        if len(numeric_values) < self._config.min_sample_size:
            logger.debug(f"Insufficient data for Z-score analysis in {column_name}")
            return []
        
        just_values = [v for _, v in numeric_values]
        data_mean = mean(just_values)
        data_stdev = stdev(just_values)
        
        if data_stdev == 0:
            return []
        
        anomalies: list[DetectedAnomaly] = []
        
        for orig_idx, value in numeric_values:
            zscore = (value - data_mean) / data_stdev
            
            if abs(zscore) > self._config.zscore_threshold:
                severity = self._zscore_to_severity(abs(zscore))
                anomalies.append(DetectedAnomaly(
                    anomaly_type=AnomalyType.NUMERIC_OUTLIER_ZSCORE,
                    severity=severity,
                    location=f"{column_name}[{orig_idx + 1}]",
                    value=value,
                    expected=f"Z-score within ±{self._config.zscore_threshold}",
                    message=f"Value {value} has Z-score {zscore:.2f}",
                    metadata={
                        "zscore": zscore,
                        "mean": data_mean,
                        "stdev": data_stdev,
                    },
                ))
        
        return anomalies

    
    def _detect_numeric_outliers(
        self,
        values: list[Any],
        column_name: str,
    ) -> list[DetectedAnomaly]:
        """Detect numeric outliers using both IQR and Z-score methods."""
        anomalies: list[DetectedAnomaly] = []
        
        # Use IQR method (more robust to outliers)
        anomalies.extend(self.detect_outliers_iqr(values, column_name))
        
        # Also use Z-score for comparison
        zscore_anomalies = self.detect_outliers_zscore(values, column_name)
        
        # Add Z-score anomalies that weren't caught by IQR
        iqr_locations = {a.location for a in anomalies}
        for anomaly in zscore_anomalies:
            if anomaly.location not in iqr_locations:
                anomalies.append(anomaly)
        
        return anomalies
    
    def _detect_missing_values(
        self,
        values: list[Any],
        column_name: str,
    ) -> list[DetectedAnomaly]:
        """Detect missing or null values in a column."""
        anomalies: list[DetectedAnomaly] = []
        
        for idx, value in enumerate(values):
            if self._is_missing(value):
                anomalies.append(DetectedAnomaly(
                    anomaly_type=AnomalyType.MISSING_VALUE,
                    severity=AnomalySeverity.MEDIUM,
                    location=f"{column_name}[{idx + 1}]",
                    value=value,
                    expected="Non-empty value",
                    message=f"Missing or empty value in {column_name}",
                    metadata={"row_index": idx},
                ))
        
        return anomalies
    
    def _detect_format_issues(
        self,
        values: list[Any],
        column_name: str,
    ) -> list[DetectedAnomaly]:
        """Detect inconsistent formatting in a column."""
        anomalies: list[DetectedAnomaly] = []
        
        # Skip if too few values
        non_empty = [v for v in values if not self._is_missing(v)]
        if len(non_empty) < 3:
            return anomalies
        
        # Detect predominant type
        type_counts: dict[str, int] = {}
        for value in non_empty:
            value_type = self._classify_value_type(value)
            type_counts[value_type] = type_counts.get(value_type, 0) + 1
        
        if not type_counts:
            return anomalies
        
        predominant_type = max(type_counts, key=type_counts.get)
        predominant_count = type_counts[predominant_type]
        
        # If less than 80% consistency, flag inconsistent values
        consistency_threshold = 0.8
        if predominant_count / len(non_empty) >= consistency_threshold:
            for idx, value in enumerate(values):
                if self._is_missing(value):
                    continue
                
                value_type = self._classify_value_type(value)
                if value_type != predominant_type:
                    anomalies.append(DetectedAnomaly(
                        anomaly_type=AnomalyType.INCONSISTENT_FORMAT,
                        severity=AnomalySeverity.LOW,
                        location=f"{column_name}[{idx + 1}]",
                        value=value,
                        expected=f"Type: {predominant_type}",
                        message=f"Value type '{value_type}' differs from column type '{predominant_type}'",
                        metadata={
                            "detected_type": value_type,
                            "expected_type": predominant_type,
                        },
                    ))
        
        return anomalies
    
    def _detect_duplicates(
        self,
        data: list[list[Any]],
        column_names: list[str],
    ) -> list[DetectedAnomaly]:
        """Detect duplicate rows in the dataset."""
        anomalies: list[DetectedAnomaly] = []
        
        # Convert rows to hashable tuples
        row_hashes: dict[tuple, list[int]] = {}
        
        for idx, row in enumerate(data):
            # Skip mostly empty rows
            non_empty = [v for v in row if not self._is_missing(v)]
            if len(non_empty) < 2:
                continue
            
            row_key = tuple(str(v) for v in row)
            if row_key not in row_hashes:
                row_hashes[row_key] = []
            row_hashes[row_key].append(idx)
        
        # Find duplicates
        for row_key, indices in row_hashes.items():
            if len(indices) > 1:
                # Mark all but the first as duplicates
                for dup_idx in indices[1:]:
                    anomalies.append(DetectedAnomaly(
                        anomaly_type=AnomalyType.DUPLICATE,
                        severity=AnomalySeverity.MEDIUM,
                        location=f"Row {dup_idx + 1}",
                        value=f"Duplicate of row {indices[0] + 1}",
                        expected="Unique row",
                        message=f"Row {dup_idx + 1} is a duplicate of row {indices[0] + 1}",
                        metadata={
                            "original_row": indices[0] + 1,
                            "duplicate_count": len(indices) - 1,
                        },
                    ))
        
        return anomalies
    
    def _detect_empty_rows(
        self,
        data: list[list[Any]],
    ) -> list[DetectedAnomaly]:
        """Detect completely empty rows."""
        anomalies: list[DetectedAnomaly] = []
        
        for idx, row in enumerate(data):
            if all(self._is_missing(v) for v in row):
                anomalies.append(DetectedAnomaly(
                    anomaly_type=AnomalyType.EMPTY_ROW,
                    severity=AnomalySeverity.LOW,
                    location=f"Row {idx + 1}",
                    value=None,
                    expected="Non-empty row",
                    message=f"Row {idx + 1} is completely empty",
                    metadata={"row_index": idx},
                ))
        
        return anomalies
    
    def _extract_numeric(
        self,
        values: Sequence[Any],
    ) -> list[tuple[int, float]]:
        """Extract numeric values with their original indices."""
        result: list[tuple[int, float]] = []
        
        for idx, value in enumerate(values):
            if value is None:
                continue
            
            try:
                if isinstance(value, (int, float)):
                    result.append((idx, float(value)))
                elif isinstance(value, str):
                    # Try to parse as number, removing common formatting
                    cleaned = re.sub(r'[$€£¥₹%,\s]', '', value)
                    if cleaned:
                        result.append((idx, float(cleaned)))
            except (ValueError, TypeError):
                continue
        
        return result
    
    def _is_missing(self, value: Any) -> bool:
        """Check if a value is considered missing."""
        if value is None:
            return True
        if isinstance(value, str):
            stripped = value.strip().lower()
            return stripped in ('', 'null', 'none', 'n/a', 'na', '-', '#n/a', '#null!')
        return False
    
    def _classify_value_type(self, value: Any) -> str:
        """Classify the type of a value."""
        if value is None:
            return "null"
        
        if isinstance(value, bool):
            return "boolean"
        
        if isinstance(value, (int, float)):
            return "numeric"
        
        if isinstance(value, str):
            value_str = value.strip()
            
            # Check for numeric
            try:
                cleaned = re.sub(r'[$€£¥₹%,\s]', '', value_str)
                if cleaned:
                    float(cleaned)
                    return "numeric"
            except ValueError:
                pass
            
            # Check for date patterns
            date_patterns = [
                r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}$',
                r'^\d{1,2}[-/]\d{1,2}[-/]\d{4}$',
                r'^\d{1,2}[-/]\d{1,2}[-/]\d{2}$',
            ]
            for pattern in date_patterns:
                if re.match(pattern, value_str):
                    return "date"
            
            # Check for boolean-like
            if value_str.lower() in ('true', 'false', 'yes', 'no', 'y', 'n'):
                return "boolean"
            
            return "text"
        
        return "unknown"
    
    def _calculate_outlier_severity(
        self,
        value: float,
        lower_bound: float,
        upper_bound: float,
        iqr: float,
    ) -> AnomalySeverity:
        """Calculate severity based on how far outside bounds."""
        if iqr == 0:
            return AnomalySeverity.MEDIUM
        
        if value < lower_bound:
            distance = (lower_bound - value) / iqr
        else:
            distance = (value - upper_bound) / iqr
        
        if distance > 3:
            return AnomalySeverity.CRITICAL
        elif distance > 2:
            return AnomalySeverity.HIGH
        elif distance > 1:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW
    
    def _zscore_to_severity(self, zscore: float) -> AnomalySeverity:
        """Convert Z-score to severity level."""
        if zscore > 5:
            return AnomalySeverity.CRITICAL
        elif zscore > 4:
            return AnomalySeverity.HIGH
        elif zscore > 3.5:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW
    
    def _col_letter(self, idx: int) -> str:
        """Convert column index to Excel-style letter."""
        result = ""
        while idx >= 0:
            result = chr(65 + idx % 26) + result
            idx = idx // 26 - 1
        return result
