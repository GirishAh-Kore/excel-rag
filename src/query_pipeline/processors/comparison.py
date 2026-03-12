"""
Comparison Query Processor Module.

This module implements the ComparisonProcessor for handling comparison
queries that compare data across files, sheets, time periods, or categories.

Key Features:
- Identify entities being compared (files, sheets, time periods, categories)
- Align data structures using common columns
- Calculate absolute and percentage differences
- Identify trends and growth rates for temporal comparisons
- Return error for incompatible structures

Supports Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

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


@dataclass
class ComparisonEntity:
    """
    Entity being compared.
    
    Attributes:
        entity_type: Type of entity (file, sheet, time_period, category).
        name: Name or identifier of the entity.
        data: Data for this entity.
        metadata: Additional metadata.
    """
    entity_type: str
    name: str
    data: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """
    Result of a comparison operation.
    
    Attributes:
        entity_a: First entity name.
        entity_b: Second entity name.
        column: Column being compared.
        value_a: Value from entity A.
        value_b: Value from entity B.
        absolute_diff: Absolute difference (A - B).
        percentage_diff: Percentage difference ((A - B) / B * 100).
        trend: Trend indicator (increase, decrease, stable).
        growth_rate: Growth rate for temporal comparisons.
    """
    entity_a: str
    entity_b: str
    column: str
    value_a: Any
    value_b: Any
    absolute_diff: Optional[float] = None
    percentage_diff: Optional[float] = None
    trend: Optional[str] = None
    growth_rate: Optional[float] = None


@register(QueryType.COMPARISON)
class ComparisonProcessor(BaseQueryProcessor):
    """
    Processor for comparison queries.
    
    Handles queries that compare data across files, sheets, time periods,
    or categories. Aligns data structures, calculates differences, and
    identifies trends.
    
    Implements Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6.
    
    Example:
        >>> processor = ComparisonProcessor()
        >>> result = processor.process(
        ...     query="Compare Q1 vs Q2 sales",
        ...     data=retrieved_data,
        ...     classification=classification
        ... )
        >>> print(result.comparison)
    """
    
    # Temporal patterns for detecting time-based comparisons
    TEMPORAL_PATTERNS = [
        r'\b(Q[1-4])\s*(?:vs\.?|versus|compared?\s*to|and)\s*(Q[1-4])\b',
        r'\b(\d{4})\s*(?:vs\.?|versus|compared?\s*to|and)\s*(\d{4})\b',
        r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s*(?:vs\.?|versus|compared?\s*to|and)\s*(January|February|March|April|May|June|July|August|September|October|November|December)\b',
        r'\b(last\s+(?:year|month|quarter|week))\s*(?:vs\.?|versus|compared?\s*to|and)\s*(this\s+(?:year|month|quarter|week))\b',
    ]
    
    def __init__(self, config: Optional[ProcessorConfig] = None) -> None:
        """
        Initialize the comparison processor.
        
        Args:
            config: Optional processor configuration.
        """
        super().__init__(config)
    
    def can_process(self, classification: QueryClassification) -> bool:
        """
        Check if this processor can handle the classification.
        
        Args:
            classification: Query classification to check.
            
        Returns:
            True if query type is COMPARISON.
        """
        return classification.query_type == QueryType.COMPARISON
    
    def get_supported_query_type(self) -> QueryType:
        """Get the supported query type."""
        return QueryType.COMPARISON
    
    def process(
        self,
        query: str,
        data: RetrievedData,
        classification: QueryClassification
    ) -> ProcessedResult:
        """
        Process a comparison query.
        
        Implements Requirements 10.1-10.6:
        - Identifies entities being compared
        - Aligns data structures using common columns
        - Calculates absolute and percentage differences
        - Identifies trends and growth rates
        - Returns error for incompatible structures
        
        Args:
            query: Original query text.
            data: Retrieved data to compare.
            classification: Query classification.
            
        Returns:
            ProcessedResult with comparison results.
        """
        logger.info(f"Processing comparison query: {query[:100]}...")
        
        try:
            # Identify entities being compared (Requirement 10.1)
            entities = self._identify_entities(query, data, classification)
            
            if len(entities) < 2:
                return ProcessedResult.error(
                    "Could not identify two entities to compare. "
                    "Please specify what you want to compare (e.g., 'Q1 vs Q2', "
                    "'2023 vs 2024', 'Product A vs Product B').",
                    source_file=data.file_name,
                    source_sheet=data.sheet_name,
                    metadata={"entities_found": len(entities)}
                )
            
            # Align data structures (Requirement 10.2)
            common_columns = self._find_common_columns(entities)
            
            if not common_columns:
                return ProcessedResult.error(
                    "The compared entities have incompatible structures. "
                    "No common columns found for comparison.",
                    source_file=data.file_name,
                    source_sheet=data.sheet_name,
                    metadata={
                        "entity_a": entities[0].name,
                        "entity_b": entities[1].name
                    }
                )
            
            # Calculate differences (Requirements 10.3, 10.4)
            comparison_results = self._calculate_differences(
                entities[0], entities[1], common_columns
            )
            
            # Identify trends for temporal comparisons (Requirement 10.4)
            is_temporal = self._is_temporal_comparison(entities)
            if is_temporal:
                comparison_results = self._add_trend_analysis(comparison_results)
            
            # Format results (Requirement 10.6)
            formatted_comparison = self._format_comparison(
                entities, comparison_results, common_columns
            )
            
            logger.info(
                f"Comparison complete: {len(comparison_results)} metrics compared"
            )
            
            return ProcessedResult(
                success=True,
                result_type="comparison",
                comparison=formatted_comparison,
                source_file=data.file_name,
                source_sheet=data.sheet_name,
                source_range=data.cell_range,
                rows_processed=sum(len(e.data) for e in entities),
                chunk_ids=data.chunk_ids,
                metadata={
                    "entity_a": entities[0].name,
                    "entity_b": entities[1].name,
                    "common_columns": common_columns,
                    "is_temporal": is_temporal,
                    "metrics_compared": len(comparison_results)
                }
            )
            
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"Comparison processing failed: {e}")
            raise ProcessingError(
                f"Failed to process comparison query: {str(e)}",
                details={"query": query, "error": str(e)}
            )

    def _identify_entities(
        self,
        query: str,
        data: RetrievedData,
        classification: QueryClassification
    ) -> list[ComparisonEntity]:
        """
        Identify entities being compared.
        
        Implements Requirement 10.1: Identify entities being compared.
        
        Args:
            query: Query text.
            data: Retrieved data.
            classification: Query classification.
            
        Returns:
            List of ComparisonEntity objects.
        """
        entities: list[ComparisonEntity] = []
        
        # Try temporal patterns first
        for pattern in self.TEMPORAL_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                entity_a_name = match.group(1)
                entity_b_name = match.group(2)
                
                # Split data by the temporal entity
                entity_a_data = self._filter_data_by_entity(
                    data.rows, data.headers, entity_a_name
                )
                entity_b_data = self._filter_data_by_entity(
                    data.rows, data.headers, entity_b_name
                )
                
                if entity_a_data and entity_b_data:
                    entities.append(ComparisonEntity(
                        entity_type="time_period",
                        name=entity_a_name,
                        data=entity_a_data
                    ))
                    entities.append(ComparisonEntity(
                        entity_type="time_period",
                        name=entity_b_name,
                        data=entity_b_data
                    ))
                    return entities
        
        # Try category-based comparison
        category_patterns = [
            r'\b(\w+)\s*(?:vs\.?|versus|compared?\s*to|and)\s*(\w+)\b',
        ]
        
        for pattern in category_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                entity_a_name, entity_b_name = match
                
                # Skip common words
                skip_words = {"the", "a", "an", "to", "from", "in", "on", "at"}
                if entity_a_name.lower() in skip_words or entity_b_name.lower() in skip_words:
                    continue
                
                entity_a_data = self._filter_data_by_entity(
                    data.rows, data.headers, entity_a_name
                )
                entity_b_data = self._filter_data_by_entity(
                    data.rows, data.headers, entity_b_name
                )
                
                if entity_a_data and entity_b_data:
                    entities.append(ComparisonEntity(
                        entity_type="category",
                        name=entity_a_name,
                        data=entity_a_data
                    ))
                    entities.append(ComparisonEntity(
                        entity_type="category",
                        name=entity_b_name,
                        data=entity_b_data
                    ))
                    return entities
        
        # Fallback: split data in half for comparison
        if len(data.rows) >= 2:
            mid = len(data.rows) // 2
            entities.append(ComparisonEntity(
                entity_type="segment",
                name="First Half",
                data=data.rows[:mid]
            ))
            entities.append(ComparisonEntity(
                entity_type="segment",
                name="Second Half",
                data=data.rows[mid:]
            ))
        
        return entities
    
    def _filter_data_by_entity(
        self,
        rows: list[dict[str, Any]],
        headers: list[str],
        entity_name: str
    ) -> list[dict[str, Any]]:
        """
        Filter data rows that match an entity name.
        
        Args:
            rows: All data rows.
            headers: Column headers.
            entity_name: Entity name to filter by.
            
        Returns:
            Filtered rows.
        """
        entity_lower = entity_name.lower()
        filtered = []
        
        for row in rows:
            for header in headers:
                value = row.get(header)
                if value is not None:
                    value_str = str(value).lower()
                    if entity_lower in value_str or value_str == entity_lower:
                        filtered.append(row)
                        break
        
        return filtered
    
    def _find_common_columns(
        self,
        entities: list[ComparisonEntity]
    ) -> list[str]:
        """
        Find columns common to all entities.
        
        Implements Requirement 10.2: Align data structures using common columns.
        
        Args:
            entities: Entities to compare.
            
        Returns:
            List of common column names.
        """
        if not entities or not entities[0].data:
            return []
        
        # Get columns from first entity
        common = set(entities[0].data[0].keys())
        
        # Intersect with columns from other entities
        for entity in entities[1:]:
            if entity.data:
                entity_columns = set(entity.data[0].keys())
                common = common.intersection(entity_columns)
        
        return list(common)
    
    def _calculate_differences(
        self,
        entity_a: ComparisonEntity,
        entity_b: ComparisonEntity,
        columns: list[str]
    ) -> list[ComparisonResult]:
        """
        Calculate differences between two entities.
        
        Implements Requirements 10.3, 10.4: Calculate absolute and percentage
        differences.
        
        Args:
            entity_a: First entity.
            entity_b: Second entity.
            columns: Columns to compare.
            
        Returns:
            List of ComparisonResult objects.
        """
        results = []
        
        # Aggregate values for each column
        agg_a = self._aggregate_entity(entity_a.data, columns)
        agg_b = self._aggregate_entity(entity_b.data, columns)
        
        for column in columns:
            value_a = agg_a.get(column)
            value_b = agg_b.get(column)
            
            result = ComparisonResult(
                entity_a=entity_a.name,
                entity_b=entity_b.name,
                column=column,
                value_a=value_a,
                value_b=value_b
            )
            
            # Calculate differences for numeric values
            if self._is_numeric(value_a) and self._is_numeric(value_b):
                num_a = self._to_float(value_a)
                num_b = self._to_float(value_b)
                
                # Absolute difference (Requirement 10.3)
                result.absolute_diff = round(num_a - num_b, self._config.numeric_precision)
                
                # Percentage difference (Requirement 10.4)
                if num_b != 0:
                    result.percentage_diff = round(
                        ((num_a - num_b) / abs(num_b)) * 100,
                        2
                    )
                
                # Determine trend
                if result.absolute_diff > 0:
                    result.trend = "increase"
                elif result.absolute_diff < 0:
                    result.trend = "decrease"
                else:
                    result.trend = "stable"
            
            results.append(result)
        
        return results
    
    def _aggregate_entity(
        self,
        rows: list[dict[str, Any]],
        columns: list[str]
    ) -> dict[str, Any]:
        """
        Aggregate values for an entity.
        
        Args:
            rows: Entity data rows.
            columns: Columns to aggregate.
            
        Returns:
            Dictionary of aggregated values.
        """
        aggregated: dict[str, Any] = {}
        
        for column in columns:
            values = [row.get(column) for row in rows if row.get(column) is not None]
            
            if not values:
                aggregated[column] = None
                continue
            
            # Check if numeric
            numeric_values = [
                self._to_float(v) for v in values if self._is_numeric(v)
            ]
            
            if numeric_values:
                # Sum for numeric columns
                aggregated[column] = sum(numeric_values)
            else:
                # Most common value for non-numeric
                from collections import Counter
                counter = Counter(str(v) for v in values)
                aggregated[column] = counter.most_common(1)[0][0]
        
        return aggregated

    def _is_temporal_comparison(
        self,
        entities: list[ComparisonEntity]
    ) -> bool:
        """
        Check if this is a temporal comparison.
        
        Args:
            entities: Entities being compared.
            
        Returns:
            True if comparing time periods.
        """
        return any(e.entity_type == "time_period" for e in entities)
    
    def _add_trend_analysis(
        self,
        results: list[ComparisonResult]
    ) -> list[ComparisonResult]:
        """
        Add trend analysis for temporal comparisons.
        
        Implements Requirement 10.4: Identify trends and growth rates.
        
        Args:
            results: Comparison results.
            
        Returns:
            Results with trend analysis added.
        """
        for result in results:
            if result.percentage_diff is not None:
                # Calculate growth rate (same as percentage diff for two periods)
                result.growth_rate = result.percentage_diff
        
        return results
    
    def _format_comparison(
        self,
        entities: list[ComparisonEntity],
        results: list[ComparisonResult],
        columns: list[str]
    ) -> dict[str, Any]:
        """
        Format comparison results for output.
        
        Implements Requirement 10.6: Format results in structured format.
        
        Args:
            entities: Compared entities.
            results: Comparison results.
            columns: Compared columns.
            
        Returns:
            Formatted comparison dictionary.
        """
        # Build comparison table
        table_rows = []
        for result in results:
            row = {
                "metric": result.column,
                entities[0].name: self._format_value(result.value_a),
                entities[1].name: self._format_value(result.value_b),
            }
            
            if result.absolute_diff is not None:
                row["difference"] = self._format_value(result.absolute_diff)
            
            if result.percentage_diff is not None:
                row["change_percent"] = f"{result.percentage_diff:+.1f}%"
            
            if result.trend:
                row["trend"] = result.trend
            
            table_rows.append(row)
        
        # Build summary
        summary_parts = []
        
        # Count increases/decreases
        increases = sum(1 for r in results if r.trend == "increase")
        decreases = sum(1 for r in results if r.trend == "decrease")
        stable = sum(1 for r in results if r.trend == "stable")
        
        if increases > 0:
            summary_parts.append(f"{increases} metric(s) increased")
        if decreases > 0:
            summary_parts.append(f"{decreases} metric(s) decreased")
        if stable > 0:
            summary_parts.append(f"{stable} metric(s) remained stable")
        
        # Find largest changes
        numeric_results = [r for r in results if r.percentage_diff is not None]
        if numeric_results:
            largest_increase = max(
                numeric_results,
                key=lambda r: r.percentage_diff or 0
            )
            largest_decrease = min(
                numeric_results,
                key=lambda r: r.percentage_diff or 0
            )
            
            if largest_increase.percentage_diff and largest_increase.percentage_diff > 0:
                summary_parts.append(
                    f"Largest increase: {largest_increase.column} "
                    f"({largest_increase.percentage_diff:+.1f}%)"
                )
            
            if largest_decrease.percentage_diff and largest_decrease.percentage_diff < 0:
                summary_parts.append(
                    f"Largest decrease: {largest_decrease.column} "
                    f"({largest_decrease.percentage_diff:+.1f}%)"
                )
        
        return {
            "entity_a": entities[0].name,
            "entity_b": entities[1].name,
            "comparison_type": entities[0].entity_type,
            "metrics_compared": len(results),
            "table": table_rows,
            "summary": ". ".join(summary_parts) + "." if summary_parts else "No significant changes detected.",
            "details": [
                {
                    "column": r.column,
                    "value_a": r.value_a,
                    "value_b": r.value_b,
                    "absolute_diff": r.absolute_diff,
                    "percentage_diff": r.percentage_diff,
                    "trend": r.trend,
                    "growth_rate": r.growth_rate
                }
                for r in results
            ]
        }
    
    def _format_value(self, value: Any) -> str:
        """
        Format a value for display.
        
        Args:
            value: Value to format.
            
        Returns:
            Formatted string.
        """
        if value is None:
            return "N/A"
        if isinstance(value, float):
            if value == int(value):
                return f"{int(value):,}"
            return f"{value:,.2f}"
        if isinstance(value, int):
            return f"{value:,}"
        return str(value)
    
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
