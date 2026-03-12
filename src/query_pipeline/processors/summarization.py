"""
Summarization Query Processor Module.

This module implements the SummarizationProcessor for generating natural
language summaries of Excel data using LLM.

Key Features:
- Generate natural language summaries using LLM
- Include key statistics (row count, column count, date range, numeric ranges)
- Identify patterns, outliers, and trends
- Use sampling for large datasets (>1000 rows)
- Limit summary to 500 words unless requested otherwise

Supports Requirements 9.1, 9.2, 9.3, 9.4, 9.5.
"""

import logging
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol, runtime_checkable

from src.exceptions import ProcessingError
from src.models.query_pipeline import QueryClassification, QueryType
from src.query_pipeline.processor_registry import register
from src.query_pipeline.processors.base import (
    BaseQueryProcessor,
    ProcessedResult,
    ProcessorConfig,
    RetrievedData,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMServiceProtocol(Protocol):
    """Protocol for LLM service dependency."""
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Generate text completion for a prompt."""
        ...


@dataclass
class DataStatistics:
    """
    Statistics computed from data for summarization.
    
    Attributes:
        row_count: Total number of rows.
        column_count: Number of columns.
        numeric_columns: List of numeric column names.
        date_columns: List of date column names.
        text_columns: List of text column names.
        numeric_stats: Statistics for each numeric column.
        date_ranges: Date ranges for each date column.
        unique_counts: Unique value counts for text columns.
        missing_counts: Missing value counts per column.
        outliers: Detected outliers per numeric column.
    """
    row_count: int = 0
    column_count: int = 0
    numeric_columns: list[str] = field(default_factory=list)
    date_columns: list[str] = field(default_factory=list)
    text_columns: list[str] = field(default_factory=list)
    numeric_stats: dict[str, dict[str, float]] = field(default_factory=dict)
    date_ranges: dict[str, dict[str, str]] = field(default_factory=dict)
    unique_counts: dict[str, int] = field(default_factory=dict)
    missing_counts: dict[str, int] = field(default_factory=dict)
    outliers: dict[str, list[float]] = field(default_factory=dict)


# System prompt for LLM summarization
SUMMARIZATION_SYSTEM_PROMPT = """You are a data analyst assistant that creates clear, 
concise summaries of Excel data. Your summaries should:

1. Start with a brief overview of what the data contains
2. Highlight key statistics and metrics
3. Identify notable patterns, trends, or anomalies
4. Be written in clear, professional language
5. Stay within the word limit specified

Focus on insights that would be valuable to someone trying to understand the data quickly.
Do not include raw data or technical details unless specifically relevant."""


SUMMARIZATION_USER_PROMPT = """Please summarize the following Excel data:

File: {file_name}
Sheet: {sheet_name}
Total Rows: {row_count}
Columns: {columns}

Key Statistics:
{statistics}

Sample Data (first few rows):
{sample_data}

{additional_context}

Please provide a summary in {max_words} words or less."""


@register(QueryType.SUMMARIZATION)
class SummarizationProcessor(BaseQueryProcessor):
    """
    Processor for summarization queries.
    
    Generates natural language summaries of Excel data using LLM.
    Computes statistics, identifies patterns and outliers, and uses
    sampling for large datasets.
    
    Implements Requirements 9.1, 9.2, 9.3, 9.4, 9.5.
    
    Example:
        >>> processor = SummarizationProcessor(llm_service=llm_svc)
        >>> result = processor.process(
        ...     query="Summarize the sales data",
        ...     data=retrieved_data,
        ...     classification=classification
        ... )
        >>> print(result.summary)
    """
    
    def __init__(
        self,
        llm_service: Optional[LLMServiceProtocol] = None,
        config: Optional[ProcessorConfig] = None
    ) -> None:
        """
        Initialize the summarization processor.
        
        Args:
            llm_service: LLM service for generating summaries.
            config: Optional processor configuration.
        """
        super().__init__(config)
        self._llm_service = llm_service
    
    def can_process(self, classification: QueryClassification) -> bool:
        """
        Check if this processor can handle the classification.
        
        Args:
            classification: Query classification to check.
            
        Returns:
            True if query type is SUMMARIZATION.
        """
        return classification.query_type == QueryType.SUMMARIZATION
    
    def get_supported_query_type(self) -> QueryType:
        """Get the supported query type."""
        return QueryType.SUMMARIZATION
    
    def process(
        self,
        query: str,
        data: RetrievedData,
        classification: QueryClassification
    ) -> ProcessedResult:
        """
        Process a summarization query.
        
        Implements Requirements 9.1-9.5:
        - Generates natural language summary using LLM
        - Includes key statistics
        - Identifies patterns, outliers, trends
        - Uses sampling for large datasets
        - Limits summary to 500 words
        
        Args:
            query: Original query text.
            data: Retrieved data to summarize.
            classification: Query classification.
            
        Returns:
            ProcessedResult with generated summary.
        """
        logger.info(f"Processing summarization query: {query[:100]}...")
        
        try:
            # Sample data if too large (Requirement 9.4)
            sample_rows, is_sampled = self._sample_data(data.rows)
            
            # Compute statistics (Requirement 9.2)
            stats = self._compute_statistics(sample_rows, data.headers, data.total_rows)
            
            # Identify patterns and outliers (Requirement 9.3)
            patterns = self._identify_patterns(sample_rows, data.headers, stats)
            
            # Determine max words (Requirement 9.5)
            max_words = self._determine_max_words(query)
            
            # Generate summary
            if self._llm_service:
                summary = self._generate_llm_summary(
                    data, sample_rows, stats, patterns, max_words
                )
            else:
                # Fallback to template-based summary
                summary = self._generate_template_summary(
                    data, stats, patterns, max_words
                )
            
            warnings = []
            if is_sampled:
                warnings.append(
                    f"Summary based on sample of {len(sample_rows)} rows "
                    f"from {data.total_rows} total rows"
                )
            
            logger.info(f"Summarization complete: {len(summary.split())} words")
            
            return ProcessedResult(
                success=True,
                result_type="summary",
                summary=summary,
                source_file=data.file_name,
                source_sheet=data.sheet_name,
                source_range=data.cell_range,
                rows_processed=len(sample_rows),
                warnings=warnings,
                chunk_ids=data.chunk_ids,
                metadata={
                    "total_rows": data.total_rows,
                    "sampled": is_sampled,
                    "sample_size": len(sample_rows),
                    "word_count": len(summary.split()),
                    "statistics": self._stats_to_dict(stats)
                }
            )
            
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"Summarization processing failed: {e}")
            raise ProcessingError(
                f"Failed to process summarization query: {str(e)}",
                details={"query": query, "error": str(e)}
            )

    def _sample_data(
        self,
        rows: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], bool]:
        """
        Sample data if it exceeds the threshold.
        
        Implements Requirement 9.4: Use sampling for large datasets.
        
        Args:
            rows: All rows.
            
        Returns:
            Tuple of (sampled rows, whether sampling was applied).
        """
        if len(rows) <= self._config.sampling_threshold:
            return rows, False
        
        # Use stratified sampling if possible, otherwise random
        sample_size = min(self._config.sample_size, len(rows))
        
        # Include first and last rows for context
        sampled = [rows[0], rows[-1]]
        
        # Random sample from the middle
        middle_rows = rows[1:-1]
        if len(middle_rows) > sample_size - 2:
            sampled.extend(random.sample(middle_rows, sample_size - 2))
        else:
            sampled.extend(middle_rows)
        
        return sampled, True
    
    def _compute_statistics(
        self,
        rows: list[dict[str, Any]],
        headers: list[str],
        total_rows: int
    ) -> DataStatistics:
        """
        Compute statistics for the data.
        
        Implements Requirement 9.2: Include key statistics.
        
        Args:
            rows: Data rows.
            headers: Column headers.
            total_rows: Total row count (before sampling).
            
        Returns:
            DataStatistics object.
        """
        stats = DataStatistics(
            row_count=total_rows,
            column_count=len(headers)
        )
        
        # Classify columns and compute stats
        for header in headers:
            values = [row.get(header) for row in rows if row.get(header) is not None]
            
            if not values:
                stats.missing_counts[header] = len(rows)
                continue
            
            # Count missing values
            missing = len(rows) - len(values)
            if missing > 0:
                stats.missing_counts[header] = missing
            
            # Determine column type and compute appropriate stats
            if self._is_numeric_column(values):
                stats.numeric_columns.append(header)
                numeric_values = [self._to_float(v) for v in values if self._is_numeric(v)]
                if numeric_values:
                    stats.numeric_stats[header] = self._compute_numeric_stats(numeric_values)
                    stats.outliers[header] = self._detect_outliers(numeric_values)
            elif self._is_date_column(values):
                stats.date_columns.append(header)
                dates = [self._parse_date(v) for v in values if self._parse_date(v)]
                if dates:
                    stats.date_ranges[header] = {
                        "min": min(dates).strftime("%Y-%m-%d"),
                        "max": max(dates).strftime("%Y-%m-%d")
                    }
            else:
                stats.text_columns.append(header)
                stats.unique_counts[header] = len(set(str(v) for v in values))
        
        return stats
    
    def _compute_numeric_stats(self, values: list[float]) -> dict[str, float]:
        """
        Compute statistics for numeric values.
        
        Args:
            values: Numeric values.
            
        Returns:
            Dictionary of statistics.
        """
        if not values:
            return {}
        
        return {
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "sum": sum(values),
            "count": len(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0
        }
    
    def _detect_outliers(self, values: list[float]) -> list[float]:
        """
        Detect outliers using IQR method.
        
        Implements Requirement 9.3: Identify outliers.
        
        Args:
            values: Numeric values.
            
        Returns:
            List of outlier values.
        """
        if len(values) < 4:
            return []
        
        sorted_values = sorted(values)
        q1_idx = len(sorted_values) // 4
        q3_idx = 3 * len(sorted_values) // 4
        
        q1 = sorted_values[q1_idx]
        q3 = sorted_values[q3_idx]
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        outliers = [v for v in values if v < lower_bound or v > upper_bound]
        return outliers[:10]  # Limit to 10 outliers
    
    def _identify_patterns(
        self,
        rows: list[dict[str, Any]],
        headers: list[str],
        stats: DataStatistics
    ) -> list[str]:
        """
        Identify patterns and trends in the data.
        
        Implements Requirement 9.3: Identify patterns and trends.
        
        Args:
            rows: Data rows.
            headers: Column headers.
            stats: Computed statistics.
            
        Returns:
            List of identified patterns.
        """
        patterns = []
        
        # Check for trends in numeric columns
        for col in stats.numeric_columns:
            values = [
                self._to_float(row.get(col))
                for row in rows
                if row.get(col) is not None and self._is_numeric(row.get(col))
            ]
            
            if len(values) >= 5:
                trend = self._detect_trend(values)
                if trend:
                    patterns.append(f"{col}: {trend}")
        
        # Check for high cardinality in text columns
        for col in stats.text_columns:
            unique = stats.unique_counts.get(col, 0)
            if unique == stats.row_count:
                patterns.append(f"{col}: appears to be a unique identifier")
            elif unique <= 5:
                patterns.append(f"{col}: categorical with {unique} distinct values")
        
        # Check for missing data patterns
        for col, missing in stats.missing_counts.items():
            if missing > stats.row_count * 0.1:
                pct = (missing / stats.row_count) * 100
                patterns.append(f"{col}: {pct:.1f}% missing values")
        
        # Check for outliers
        for col, outliers in stats.outliers.items():
            if outliers:
                patterns.append(f"{col}: {len(outliers)} outlier(s) detected")
        
        return patterns
    
    def _detect_trend(self, values: list[float]) -> Optional[str]:
        """
        Detect trend in a sequence of values.
        
        Args:
            values: Sequence of numeric values.
            
        Returns:
            Trend description or None.
        """
        if len(values) < 3:
            return None
        
        # Simple linear trend detection
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return None
        
        slope = numerator / denominator
        
        # Normalize slope by mean to get relative change
        if y_mean != 0:
            relative_slope = slope / abs(y_mean)
        else:
            relative_slope = slope
        
        if relative_slope > 0.1:
            return "increasing trend"
        elif relative_slope < -0.1:
            return "decreasing trend"
        
        return None

    def _determine_max_words(self, query: str) -> int:
        """
        Determine maximum words for summary.
        
        Implements Requirement 9.5: Limit to 500 words unless requested.
        
        Args:
            query: Query text.
            
        Returns:
            Maximum word count.
        """
        query_lower = query.lower()
        
        # Check for explicit length requests
        if "detailed" in query_lower or "comprehensive" in query_lower:
            return 1000
        if "brief" in query_lower or "short" in query_lower:
            return 200
        
        return self._config.max_summary_words
    
    def _generate_llm_summary(
        self,
        data: RetrievedData,
        sample_rows: list[dict[str, Any]],
        stats: DataStatistics,
        patterns: list[str],
        max_words: int
    ) -> str:
        """
        Generate summary using LLM.
        
        Implements Requirement 9.1: Generate natural language summary.
        
        Args:
            data: Retrieved data.
            sample_rows: Sampled rows.
            stats: Computed statistics.
            patterns: Identified patterns.
            max_words: Maximum word count.
            
        Returns:
            Generated summary.
        """
        # Format statistics for prompt
        stats_text = self._format_statistics_for_prompt(stats)
        
        # Format sample data
        sample_text = self._format_sample_data(sample_rows[:5], data.headers)
        
        # Format patterns
        patterns_text = ""
        if patterns:
            patterns_text = "\nIdentified Patterns:\n" + "\n".join(f"- {p}" for p in patterns)
        
        prompt = SUMMARIZATION_USER_PROMPT.format(
            file_name=data.file_name,
            sheet_name=data.sheet_name,
            row_count=stats.row_count,
            columns=", ".join(data.headers),
            statistics=stats_text,
            sample_data=sample_text,
            additional_context=patterns_text,
            max_words=max_words
        )
        
        try:
            summary = self._llm_service.generate(
                prompt=prompt,
                system_prompt=SUMMARIZATION_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=max_words * 2  # Rough token estimate
            )
            return summary.strip()
        except Exception as e:
            logger.warning(f"LLM summary generation failed: {e}, using template")
            return self._generate_template_summary(data, stats, patterns, max_words)
    
    def _generate_template_summary(
        self,
        data: RetrievedData,
        stats: DataStatistics,
        patterns: list[str],
        max_words: int
    ) -> str:
        """
        Generate summary using template (fallback when LLM unavailable).
        
        Args:
            data: Retrieved data.
            stats: Computed statistics.
            patterns: Identified patterns.
            max_words: Maximum word count.
            
        Returns:
            Generated summary.
        """
        parts = []
        
        # Overview
        parts.append(
            f"This data from '{data.file_name}' (sheet: {data.sheet_name}) "
            f"contains {stats.row_count:,} rows and {stats.column_count} columns."
        )
        
        # Column types
        if stats.numeric_columns:
            parts.append(
                f"Numeric columns: {', '.join(stats.numeric_columns[:5])}"
                + ("..." if len(stats.numeric_columns) > 5 else ".")
            )
        
        if stats.date_columns:
            parts.append(f"Date columns: {', '.join(stats.date_columns)}.")
        
        # Key statistics
        for col, col_stats in list(stats.numeric_stats.items())[:3]:
            parts.append(
                f"{col}: ranges from {col_stats['min']:,.2f} to {col_stats['max']:,.2f} "
                f"(mean: {col_stats['mean']:,.2f})."
            )
        
        # Date ranges
        for col, date_range in stats.date_ranges.items():
            parts.append(
                f"{col}: spans from {date_range['min']} to {date_range['max']}."
            )
        
        # Patterns
        if patterns:
            parts.append("Notable observations:")
            for pattern in patterns[:5]:
                parts.append(f"- {pattern}")
        
        summary = " ".join(parts)
        
        # Truncate if too long
        words = summary.split()
        if len(words) > max_words:
            summary = " ".join(words[:max_words]) + "..."
        
        return summary
    
    def _format_statistics_for_prompt(self, stats: DataStatistics) -> str:
        """Format statistics for LLM prompt."""
        lines = []
        
        for col, col_stats in stats.numeric_stats.items():
            lines.append(
                f"- {col}: min={col_stats['min']:.2f}, max={col_stats['max']:.2f}, "
                f"mean={col_stats['mean']:.2f}, median={col_stats['median']:.2f}"
            )
        
        for col, date_range in stats.date_ranges.items():
            lines.append(f"- {col}: {date_range['min']} to {date_range['max']}")
        
        for col, unique in list(stats.unique_counts.items())[:5]:
            lines.append(f"- {col}: {unique} unique values")
        
        return "\n".join(lines) if lines else "No detailed statistics available."
    
    def _format_sample_data(
        self,
        rows: list[dict[str, Any]],
        headers: list[str]
    ) -> str:
        """Format sample data for LLM prompt."""
        if not rows:
            return "No sample data available."
        
        lines = [" | ".join(headers[:8])]  # Limit columns
        lines.append("-" * 50)
        
        for row in rows[:5]:
            values = [str(row.get(h, ""))[:20] for h in headers[:8]]
            lines.append(" | ".join(values))
        
        return "\n".join(lines)
    
    def _stats_to_dict(self, stats: DataStatistics) -> dict[str, Any]:
        """Convert DataStatistics to dictionary for metadata."""
        return {
            "row_count": stats.row_count,
            "column_count": stats.column_count,
            "numeric_columns": stats.numeric_columns,
            "date_columns": stats.date_columns,
            "text_columns": stats.text_columns,
            "outlier_counts": {k: len(v) for k, v in stats.outliers.items()}
        }
    
    # Helper methods for type detection
    
    def _is_numeric_column(self, values: list[Any]) -> bool:
        """Check if column contains mostly numeric values."""
        numeric_count = sum(1 for v in values if self._is_numeric(v))
        return numeric_count / len(values) > 0.5 if values else False
    
    def _is_date_column(self, values: list[Any]) -> bool:
        """Check if column contains mostly date values."""
        date_count = sum(1 for v in values if self._parse_date(v) is not None)
        return date_count / len(values) > 0.5 if values else False
    
    def _is_numeric(self, value: Any) -> bool:
        """Check if value is numeric."""
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            try:
                float(value.replace(",", "").replace("$", "").replace("%", ""))
                return True
            except ValueError:
                return False
        return False
    
    def _to_float(self, value: Any) -> float:
        """Convert value to float."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace(",", "").replace("$", "").replace("%", "")
            return float(cleaned)
        return 0.0
    
    def _parse_date(self, value: Any) -> Optional[datetime]:
        """Try to parse value as date."""
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            return None
        
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None
