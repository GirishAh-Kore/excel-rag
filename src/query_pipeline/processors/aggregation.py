"""
Aggregation Query Processor Module.

This module implements the AggregationProcessor for handling aggregation
queries (SUM, AVERAGE, COUNT, MIN, MAX, MEDIAN) on Excel data.

Key Features:
- Supports all standard aggregation functions
- Filter condition parsing and application
- Numeric data type validation with warnings for non-numeric values
- Returns computed value, rows processed, and rows skipped

Supports Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6.
"""

import logging
import re
import statistics
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional

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


# Supported aggregation functions
AGGREGATION_FUNCTIONS: set[str] = {"SUM", "AVERAGE", "COUNT", "MIN", "MAX", "MEDIAN"}


@dataclass
class FilterCondition:
    """
    Parsed filter condition for aggregation.
    
    Attributes:
        column: Column name to filter on.
        operator: Comparison operator (=, !=, <, >, <=, >=, contains).
        value: Value to compare against.
        is_numeric: Whether the value is numeric.
    """
    column: str
    operator: str
    value: Any
    is_numeric: bool = False


@register(QueryType.AGGREGATION)
class AggregationProcessor(BaseQueryProcessor):
    """
    Processor for aggregation queries.
    
    Handles SUM, AVERAGE, COUNT, MIN, MAX, MEDIAN functions with
    filter condition support. Validates numeric data types and
    skips non-numeric values with warnings.
    
    Implements Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6.
    
    Example:
        >>> processor = AggregationProcessor()
        >>> result = processor.process(
        ...     query="What is the total sales for Q1?",
        ...     data=retrieved_data,
        ...     classification=classification
        ... )
        >>> print(result.value)  # 1234567.89
    """
    
    def __init__(self, config: Optional[ProcessorConfig] = None) -> None:
        """
        Initialize the aggregation processor.
        
        Args:
            config: Optional processor configuration.
        """
        super().__init__(config)
        
        # Map function names to implementations
        self._function_map: dict[str, Callable[[list[float]], float]] = {
            "SUM": self._compute_sum,
            "AVERAGE": self._compute_average,
            "COUNT": self._compute_count,
            "MIN": self._compute_min,
            "MAX": self._compute_max,
            "MEDIAN": self._compute_median,
        }
    
    def can_process(self, classification: QueryClassification) -> bool:
        """
        Check if this processor can handle the classification.
        
        Args:
            classification: Query classification to check.
            
        Returns:
            True if query type is AGGREGATION.
        """
        return classification.query_type == QueryType.AGGREGATION
    
    def get_supported_query_type(self) -> QueryType:
        """Get the supported query type."""
        return QueryType.AGGREGATION
    
    def process(
        self,
        query: str,
        data: RetrievedData,
        classification: QueryClassification
    ) -> ProcessedResult:
        """
        Process an aggregation query.
        
        Implements Requirements 7.1-7.6:
        - Identifies target column(s) and aggregation function(s)
        - Supports SUM, AVERAGE, COUNT, MIN, MAX, MEDIAN
        - Applies filter conditions
        - Validates numeric data types
        - Returns computed value, rows processed, rows skipped
        
        Args:
            query: Original query text.
            data: Retrieved data to aggregate.
            classification: Query classification with detected aggregations.
            
        Returns:
            ProcessedResult with computed aggregation value.
            
        Raises:
            ProcessingError: If aggregation fails.
        """
        logger.info(f"Processing aggregation query: {query[:100]}...")
        
        try:
            # Determine aggregation function
            agg_function = self._determine_aggregation_function(
                query, classification
            )
            
            # Determine target column
            target_column = self._determine_target_column(
                query, data, classification
            )
            
            # Parse and apply filters
            filters = self._parse_filters(query, classification, data.headers)
            filtered_rows = self._apply_filters(data.rows, filters)
            
            # Extract numeric values from target column
            values, rows_skipped, warnings = self._extract_numeric_values(
                filtered_rows, target_column
            )
            
            # Check if we have any values to aggregate
            if not values and agg_function != "COUNT":
                return ProcessedResult.error(
                    f"Column '{target_column}' contains no numeric values",
                    source_file=data.file_name,
                    source_sheet=data.sheet_name,
                    source_range=data.cell_range,
                    metadata={
                        "column": target_column,
                        "aggregation_function": agg_function,
                        "rows_checked": len(filtered_rows)
                    }
                )
            
            # Compute aggregation
            if agg_function == "COUNT":
                # COUNT can work on any data type
                result_value = len(filtered_rows)
            else:
                compute_func = self._function_map[agg_function]
                result_value = compute_func(values)
            
            # Round to configured precision
            if isinstance(result_value, float):
                result_value = round(result_value, self._config.numeric_precision)
            
            logger.info(
                f"Aggregation complete: {agg_function}({target_column}) = "
                f"{result_value}, processed {len(values)} values, "
                f"skipped {rows_skipped}"
            )
            
            return ProcessedResult.aggregation(
                value=result_value,
                source_file=data.file_name,
                source_sheet=data.sheet_name,
                source_range=data.cell_range,
                rows_processed=len(values) if agg_function != "COUNT" else len(filtered_rows),
                rows_skipped=rows_skipped,
                warnings=warnings,
                chunk_ids=data.chunk_ids,
                metadata={
                    "aggregation_function": agg_function,
                    "target_column": target_column,
                    "filters_applied": len(filters),
                    "total_rows_before_filter": len(data.rows),
                    "rows_after_filter": len(filtered_rows)
                }
            )
            
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"Aggregation processing failed: {e}")
            raise ProcessingError(
                f"Failed to process aggregation query: {str(e)}",
                details={
                    "query": query,
                    "error": str(e)
                }
            )
    
    def _determine_aggregation_function(
        self,
        query: str,
        classification: QueryClassification
    ) -> str:
        """
        Determine which aggregation function to use.
        
        Args:
            query: Query text.
            classification: Query classification.
            
        Returns:
            Aggregation function name (SUM, AVERAGE, etc.).
        """
        # Check classification first
        if classification.detected_aggregations:
            func = classification.detected_aggregations[0].upper()
            if func in AGGREGATION_FUNCTIONS:
                return func
        
        # Fall back to pattern matching
        query_lower = query.lower()
        
        patterns = [
            (r'\b(sum|total)\b', "SUM"),
            (r'\b(average|avg|mean)\b', "AVERAGE"),
            (r'\b(count|how many|number of)\b', "COUNT"),
            (r'\b(min|minimum|lowest|smallest)\b', "MIN"),
            (r'\b(max|maximum|highest|largest|biggest)\b', "MAX"),
            (r'\b(median)\b', "MEDIAN"),
        ]
        
        for pattern, func in patterns:
            if re.search(pattern, query_lower):
                return func
        
        # Default to SUM if no specific function detected
        return "SUM"
    
    def _determine_target_column(
        self,
        query: str,
        data: RetrievedData,
        classification: QueryClassification
    ) -> str:
        """
        Determine which column to aggregate.
        
        Args:
            query: Query text.
            data: Retrieved data.
            classification: Query classification.
            
        Returns:
            Column name to aggregate.
            
        Raises:
            ProcessingError: If no suitable column found.
        """
        # Check classification for detected columns
        if classification.detected_columns:
            for col in classification.detected_columns:
                # Find matching header (case-insensitive)
                for header in data.headers:
                    if col.lower() == header.lower():
                        return header
                    if col.lower() in header.lower():
                        return header
        
        # Try to find column mentioned in query
        query_lower = query.lower()
        for header in data.headers:
            if header.lower() in query_lower:
                return header
        
        # Look for common numeric column names
        numeric_indicators = [
            "amount", "total", "sum", "value", "price", "cost",
            "revenue", "sales", "quantity", "count", "number"
        ]
        
        for indicator in numeric_indicators:
            for header in data.headers:
                if indicator in header.lower():
                    return header
        
        # If only one numeric column, use it
        numeric_columns = self._find_numeric_columns(data)
        if len(numeric_columns) == 1:
            return numeric_columns[0]
        
        # If multiple numeric columns, prefer first one
        if numeric_columns:
            return numeric_columns[0]
        
        raise ProcessingError(
            "Could not determine target column for aggregation",
            details={
                "available_columns": data.headers,
                "detected_columns": classification.detected_columns,
                "query": query
            }
        )
    
    def _find_numeric_columns(self, data: RetrievedData) -> list[str]:
        """
        Find columns that contain numeric data.
        
        Args:
            data: Retrieved data.
            
        Returns:
            List of column names with numeric data.
        """
        numeric_columns = []
        
        for header in data.headers:
            numeric_count = 0
            total_count = 0
            
            for row in data.rows[:min(10, len(data.rows))]:  # Sample first 10 rows
                value = row.get(header)
                if value is not None:
                    total_count += 1
                    if self._is_numeric(value):
                        numeric_count += 1
            
            # Consider column numeric if >50% of sampled values are numeric
            if total_count > 0 and numeric_count / total_count > 0.5:
                numeric_columns.append(header)
        
        return numeric_columns
    
    def _parse_filters(
        self,
        query: str,
        classification: QueryClassification,
        headers: list[str]
    ) -> list[FilterCondition]:
        """
        Parse filter conditions from query.
        
        Implements Requirement 7.3: Apply filter conditions before aggregation.
        
        Args:
            query: Query text.
            classification: Query classification.
            headers: Available column headers.
            
        Returns:
            List of parsed filter conditions.
        """
        filters: list[FilterCondition] = []
        
        # Use detected filters from classification
        for filter_text in classification.detected_filters:
            parsed = self._parse_single_filter(filter_text, headers)
            if parsed:
                filters.append(parsed)
        
        # Also try to extract filters from query directly
        filter_patterns = [
            # "for X" pattern
            r'\bfor\s+([^,\.]+)',
            # "where X = Y" pattern
            r'\bwhere\s+(\w+)\s*(=|!=|<|>|<=|>=)\s*([^\s,\.]+)',
            # "with X" pattern
            r'\bwith\s+(\w+)\s+([^\s,\.]+)',
        ]
        
        for pattern in filter_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) == 3:
                        # where X = Y pattern
                        column, operator, value = match
                        for header in headers:
                            if column.lower() in header.lower():
                                filters.append(FilterCondition(
                                    column=header,
                                    operator=operator,
                                    value=self._parse_value(value),
                                    is_numeric=self._is_numeric(value)
                                ))
                                break
        
        return filters
    
    def _parse_single_filter(
        self,
        filter_text: str,
        headers: list[str]
    ) -> Optional[FilterCondition]:
        """
        Parse a single filter text into a FilterCondition.
        
        Args:
            filter_text: Filter text to parse.
            headers: Available column headers.
            
        Returns:
            FilterCondition or None if parsing fails.
        """
        # Try "column = value" pattern
        match = re.match(r'(\w+)\s*(=|!=|<|>|<=|>=)\s*(.+)', filter_text.strip())
        if match:
            column, operator, value = match.groups()
            for header in headers:
                if column.lower() in header.lower():
                    return FilterCondition(
                        column=header,
                        operator=operator,
                        value=self._parse_value(value.strip()),
                        is_numeric=self._is_numeric(value.strip())
                    )
        
        # Try to match filter text against headers for equality
        filter_lower = filter_text.lower().strip()
        for header in headers:
            if header.lower() in filter_lower:
                # Extract value after header name
                remaining = filter_lower.replace(header.lower(), "").strip()
                if remaining:
                    return FilterCondition(
                        column=header,
                        operator="contains",
                        value=remaining,
                        is_numeric=False
                    )
        
        return None
    
    def _parse_value(self, value: str) -> Any:
        """
        Parse a string value into appropriate type.
        
        Args:
            value: String value to parse.
            
        Returns:
            Parsed value (int, float, or string).
        """
        value = value.strip().strip('"\'')
        
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        return value
    
    def _apply_filters(
        self,
        rows: list[dict[str, Any]],
        filters: list[FilterCondition]
    ) -> list[dict[str, Any]]:
        """
        Apply filter conditions to rows.
        
        Args:
            rows: Rows to filter.
            filters: Filter conditions to apply.
            
        Returns:
            Filtered rows.
        """
        if not filters:
            return rows
        
        filtered = []
        for row in rows:
            if self._row_matches_filters(row, filters):
                filtered.append(row)
        
        return filtered
    
    def _row_matches_filters(
        self,
        row: dict[str, Any],
        filters: list[FilterCondition]
    ) -> bool:
        """
        Check if a row matches all filter conditions.
        
        Args:
            row: Row to check.
            filters: Filter conditions.
            
        Returns:
            True if row matches all filters.
        """
        for filter_cond in filters:
            value = row.get(filter_cond.column)
            if value is None:
                return False
            
            if not self._value_matches_filter(value, filter_cond):
                return False
        
        return True
    
    def _value_matches_filter(
        self,
        value: Any,
        filter_cond: FilterCondition
    ) -> bool:
        """
        Check if a value matches a filter condition.
        
        Args:
            value: Value to check.
            filter_cond: Filter condition.
            
        Returns:
            True if value matches filter.
        """
        filter_value = filter_cond.value
        operator = filter_cond.operator
        
        # Convert to comparable types
        if filter_cond.is_numeric and self._is_numeric(value):
            value = float(self._to_numeric(value))
            filter_value = float(filter_value)
        else:
            value = str(value).lower()
            filter_value = str(filter_value).lower()
        
        if operator == "=":
            return value == filter_value
        elif operator == "!=":
            return value != filter_value
        elif operator == "<":
            return value < filter_value
        elif operator == ">":
            return value > filter_value
        elif operator == "<=":
            return value <= filter_value
        elif operator == ">=":
            return value >= filter_value
        elif operator == "contains":
            return filter_value in str(value).lower()
        
        return False
    
    def _extract_numeric_values(
        self,
        rows: list[dict[str, Any]],
        column: str
    ) -> tuple[list[float], int, list[str]]:
        """
        Extract numeric values from a column.
        
        Implements Requirement 7.4: Handle numeric data type validation
        and skip non-numeric values with warning.
        
        Args:
            rows: Rows to extract from.
            column: Column name.
            
        Returns:
            Tuple of (numeric values, rows skipped, warnings).
        """
        values: list[float] = []
        skipped = 0
        warnings: list[str] = []
        non_numeric_samples: list[str] = []
        
        for row in rows:
            raw_value = row.get(column)
            
            if raw_value is None:
                skipped += 1
                continue
            
            if self._is_numeric(raw_value):
                values.append(float(self._to_numeric(raw_value)))
            else:
                skipped += 1
                if len(non_numeric_samples) < 3:
                    non_numeric_samples.append(str(raw_value)[:50])
        
        if skipped > 0:
            warning_msg = (
                f"Skipped {skipped} non-numeric value(s) in column '{column}'"
            )
            if non_numeric_samples:
                warning_msg += f". Examples: {non_numeric_samples}"
            warnings.append(warning_msg)
            logger.warning(warning_msg)
        
        return values, skipped, warnings
    
    def _is_numeric(self, value: Any) -> bool:
        """
        Check if a value is numeric.
        
        Args:
            value: Value to check.
            
        Returns:
            True if value is numeric.
        """
        if isinstance(value, (int, float, Decimal)):
            return True
        
        if isinstance(value, str):
            # Remove common formatting
            cleaned = value.strip()
            cleaned = cleaned.replace(",", "")
            cleaned = cleaned.replace("$", "")
            cleaned = cleaned.replace("€", "")
            cleaned = cleaned.replace("£", "")
            cleaned = cleaned.replace("%", "")
            cleaned = cleaned.strip()
            
            if not cleaned:
                return False
            
            try:
                float(cleaned)
                return True
            except ValueError:
                return False
        
        return False
    
    def _to_numeric(self, value: Any) -> float:
        """
        Convert a value to numeric.
        
        Args:
            value: Value to convert.
            
        Returns:
            Numeric value.
        """
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, Decimal):
            return float(value)
        
        if isinstance(value, str):
            cleaned = value.strip()
            cleaned = cleaned.replace(",", "")
            cleaned = cleaned.replace("$", "")
            cleaned = cleaned.replace("€", "")
            cleaned = cleaned.replace("£", "")
            
            # Handle percentages
            if cleaned.endswith("%"):
                cleaned = cleaned[:-1]
                return float(cleaned) / 100
            
            return float(cleaned)
        
        return float(value)
    
    # Aggregation function implementations
    
    def _compute_sum(self, values: list[float]) -> float:
        """Compute sum of values."""
        return sum(values)
    
    def _compute_average(self, values: list[float]) -> float:
        """Compute average of values."""
        if not values:
            return 0.0
        return sum(values) / len(values)
    
    def _compute_count(self, values: list[float]) -> float:
        """Compute count of values."""
        return float(len(values))
    
    def _compute_min(self, values: list[float]) -> float:
        """Compute minimum of values."""
        if not values:
            return 0.0
        return min(values)
    
    def _compute_max(self, values: list[float]) -> float:
        """Compute maximum of values."""
        if not values:
            return 0.0
        return max(values)
    
    def _compute_median(self, values: list[float]) -> float:
        """Compute median of values."""
        if not values:
            return 0.0
        return statistics.median(values)
