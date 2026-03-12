"""
Lookup Query Processor Module.

This module implements the LookupProcessor for handling lookup queries
that retrieve specific values, rows, or data points from Excel data.

Key Features:
- Support lookups by row criteria, column name, cell reference
- Return all matching rows up to configurable limit
- Preserve original data formatting (dates, currency, percentages)
- Suggest similar values when no matches found

Supports Requirements 8.1, 8.2, 8.3, 8.4, 8.5.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
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
class LookupCriteria:
    """
    Parsed lookup criteria.
    
    Attributes:
        column: Column to search in (None for any column).
        value: Value to search for.
        operator: Match operator (exact, contains, starts_with, ends_with).
        cell_reference: Direct cell reference if specified (e.g., "A1").
    """
    column: Optional[str]
    value: Any
    operator: str = "contains"
    cell_reference: Optional[str] = None


@register(QueryType.LOOKUP)
class LookupProcessor(BaseQueryProcessor):
    """
    Processor for lookup queries.
    
    Handles queries that retrieve specific values, rows, or data points.
    Supports lookups by row criteria, column name, and cell reference.
    Preserves original data formatting and suggests similar values when
    no matches are found.
    
    Implements Requirements 8.1, 8.2, 8.3, 8.4, 8.5.
    
    Example:
        >>> processor = LookupProcessor()
        >>> result = processor.process(
        ...     query="What is the price of Product A?",
        ...     data=retrieved_data,
        ...     classification=classification
        ... )
        >>> print(result.rows)  # [{"Product": "Product A", "Price": "$99.99"}]
    """
    
    # Common date formats for preservation
    DATE_FORMATS = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%B %d, %Y",
        "%b %d, %Y",
    ]
    
    def __init__(self, config: Optional[ProcessorConfig] = None) -> None:
        """
        Initialize the lookup processor.
        
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
            True if query type is LOOKUP.
        """
        return classification.query_type == QueryType.LOOKUP
    
    def get_supported_query_type(self) -> QueryType:
        """Get the supported query type."""
        return QueryType.LOOKUP
    
    def process(
        self,
        query: str,
        data: RetrievedData,
        classification: QueryClassification
    ) -> ProcessedResult:
        """
        Process a lookup query.
        
        Implements Requirements 8.1-8.5:
        - Identifies target cell, row, or column
        - Supports lookups by row criteria, column name, cell reference
        - Returns all matching rows up to limit
        - Suggests similar values if no matches
        - Preserves original data formatting
        
        Args:
            query: Original query text.
            data: Retrieved data to search.
            classification: Query classification.
            
        Returns:
            ProcessedResult with matching rows.
        """
        logger.info(f"Processing lookup query: {query[:100]}...")
        
        try:
            # Parse lookup criteria from query
            criteria = self._parse_lookup_criteria(query, data, classification)
            
            # Handle cell reference lookup
            if criteria.cell_reference:
                return self._lookup_by_cell_reference(
                    criteria.cell_reference, data
                )
            
            # Find matching rows
            matches = self._find_matches(data.rows, criteria, data.headers)
            
            # If no matches, suggest similar values
            if not matches:
                suggestions = self._find_similar_values(
                    criteria.value, data.rows, criteria.column, data.headers
                )
                
                warning_msg = f"No rows match the criteria: {criteria.value}"
                if suggestions:
                    warning_msg += f". Did you mean: {', '.join(suggestions[:3])}?"
                
                return ProcessedResult(
                    success=True,
                    result_type="rows",
                    rows=[],
                    source_file=data.file_name,
                    source_sheet=data.sheet_name,
                    source_range=data.cell_range,
                    rows_processed=len(data.rows),
                    warnings=[warning_msg],
                    chunk_ids=data.chunk_ids,
                    metadata={
                        "criteria": str(criteria.value),
                        "suggestions": suggestions[:5] if suggestions else []
                    }
                )
            
            # Limit results
            total_matches = len(matches)
            limited_matches = matches[:self._config.max_results]
            
            # Format results preserving original formatting
            formatted_rows = [
                self._format_row(row, data.headers) for row in limited_matches
            ]
            
            warnings = []
            if total_matches > self._config.max_results:
                warnings.append(
                    f"Showing {self._config.max_results} of {total_matches} "
                    f"matching rows"
                )
            
            logger.info(
                f"Lookup complete: found {total_matches} matches, "
                f"returning {len(formatted_rows)}"
            )
            
            return ProcessedResult.lookup(
                rows=formatted_rows,
                source_file=data.file_name,
                source_sheet=data.sheet_name,
                source_range=data.cell_range,
                total_matches=total_matches,
                warnings=warnings,
                chunk_ids=data.chunk_ids,
                metadata={
                    "criteria_column": criteria.column,
                    "criteria_value": str(criteria.value),
                    "match_operator": criteria.operator
                }
            )
            
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"Lookup processing failed: {e}")
            raise ProcessingError(
                f"Failed to process lookup query: {str(e)}",
                details={"query": query, "error": str(e)}
            )

    def _parse_lookup_criteria(
        self,
        query: str,
        data: RetrievedData,
        classification: QueryClassification
    ) -> LookupCriteria:
        """
        Parse lookup criteria from query.
        
        Args:
            query: Query text.
            data: Retrieved data.
            classification: Query classification.
            
        Returns:
            Parsed LookupCriteria.
        """
        # Check for cell reference (e.g., "A1", "B10")
        cell_ref_match = re.search(r'\b([A-Z]+\d+)\b', query)
        if cell_ref_match:
            return LookupCriteria(
                column=None,
                value=None,
                cell_reference=cell_ref_match.group(1)
            )
        
        # Try to extract column and value from query
        column = None
        value = None
        operator = "contains"
        
        # Check detected columns from classification
        if classification.detected_columns:
            for col in classification.detected_columns:
                for header in data.headers:
                    if col.lower() == header.lower() or col.lower() in header.lower():
                        column = header
                        break
                if column:
                    break
        
        # Extract value patterns
        value_patterns = [
            # "for X" pattern
            r'\bfor\s+["\']?([^"\',.?]+)["\']?',
            # "of X" pattern
            r'\bof\s+["\']?([^"\',.?]+)["\']?',
            # "named X" pattern
            r'\bnamed\s+["\']?([^"\',.?]+)["\']?',
            # "called X" pattern
            r'\bcalled\s+["\']?([^"\',.?]+)["\']?',
            # Quoted value
            r'["\']([^"\']+)["\']',
            # "X's" pattern (possessive)
            r'\b(\w+)\'s\b',
        ]
        
        for pattern in value_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                break
        
        # If no value found, try to extract from filters
        if not value and classification.detected_filters:
            value = classification.detected_filters[0]
        
        # If still no value, use the query itself (simplified)
        if not value:
            # Remove common question words
            simplified = re.sub(
                r'\b(what|where|which|who|show|find|get|is|are|the|a|an)\b',
                '',
                query,
                flags=re.IGNORECASE
            )
            simplified = simplified.strip()
            if simplified:
                value = simplified
        
        return LookupCriteria(
            column=column,
            value=value or "",
            operator=operator
        )
    
    def _lookup_by_cell_reference(
        self,
        cell_ref: str,
        data: RetrievedData
    ) -> ProcessedResult:
        """
        Look up value by cell reference.
        
        Args:
            cell_ref: Cell reference (e.g., "A1").
            data: Retrieved data.
            
        Returns:
            ProcessedResult with cell value.
        """
        # Parse cell reference
        match = re.match(r'([A-Z]+)(\d+)', cell_ref)
        if not match:
            return ProcessedResult.error(
                f"Invalid cell reference: {cell_ref}",
                source_file=data.file_name,
                source_sheet=data.sheet_name
            )
        
        col_letters = match.group(1)
        row_num = int(match.group(2))
        
        # Convert column letters to index
        col_index = 0
        for char in col_letters:
            col_index = col_index * 26 + (ord(char) - ord('A') + 1)
        col_index -= 1  # 0-based
        
        # Check bounds
        if col_index >= len(data.headers):
            return ProcessedResult.error(
                f"Column {col_letters} is out of range",
                source_file=data.file_name,
                source_sheet=data.sheet_name,
                metadata={"available_columns": len(data.headers)}
            )
        
        # Row 1 is typically headers, so data starts at row 2
        row_index = row_num - 2  # Adjust for 0-based and header row
        
        if row_index < 0 or row_index >= len(data.rows):
            return ProcessedResult.error(
                f"Row {row_num} is out of range",
                source_file=data.file_name,
                source_sheet=data.sheet_name,
                metadata={"available_rows": len(data.rows) + 1}
            )
        
        column_name = data.headers[col_index]
        value = data.rows[row_index].get(column_name)
        
        formatted_value = self._format_value(value)
        
        return ProcessedResult.lookup(
            rows=[{column_name: formatted_value}],
            source_file=data.file_name,
            source_sheet=data.sheet_name,
            source_range=cell_ref,
            total_matches=1,
            chunk_ids=data.chunk_ids,
            metadata={"cell_reference": cell_ref, "column": column_name}
        )

    def _find_matches(
        self,
        rows: list[dict[str, Any]],
        criteria: LookupCriteria,
        headers: list[str]
    ) -> list[dict[str, Any]]:
        """
        Find rows matching the lookup criteria.
        
        Args:
            rows: Rows to search.
            criteria: Lookup criteria.
            headers: Column headers.
            
        Returns:
            List of matching rows.
        """
        matches = []
        search_value = str(criteria.value).lower() if criteria.value else ""
        
        for row in rows:
            if criteria.column:
                # Search specific column
                cell_value = row.get(criteria.column)
                if self._value_matches(cell_value, search_value, criteria.operator):
                    matches.append(row)
            else:
                # Search all columns
                for header in headers:
                    cell_value = row.get(header)
                    if self._value_matches(cell_value, search_value, criteria.operator):
                        matches.append(row)
                        break
        
        return matches
    
    def _value_matches(
        self,
        cell_value: Any,
        search_value: str,
        operator: str
    ) -> bool:
        """
        Check if a cell value matches the search criteria.
        
        Args:
            cell_value: Value to check.
            search_value: Value to search for.
            operator: Match operator.
            
        Returns:
            True if value matches.
        """
        if cell_value is None:
            return False
        
        cell_str = str(cell_value).lower()
        
        if operator == "exact":
            return cell_str == search_value
        elif operator == "contains":
            return search_value in cell_str
        elif operator == "starts_with":
            return cell_str.startswith(search_value)
        elif operator == "ends_with":
            return cell_str.endswith(search_value)
        
        return False
    
    def _find_similar_values(
        self,
        search_value: Any,
        rows: list[dict[str, Any]],
        column: Optional[str],
        headers: list[str]
    ) -> list[str]:
        """
        Find similar values when no exact match is found.
        
        Implements Requirement 8.4: Suggest similar values if available.
        
        Args:
            search_value: Value that was searched for.
            rows: All rows.
            column: Column to search (None for all).
            headers: Column headers.
            
        Returns:
            List of similar values.
        """
        if not search_value:
            return []
        
        search_str = str(search_value).lower()
        candidates: dict[str, float] = {}
        
        columns_to_check = [column] if column else headers
        
        for row in rows:
            for col in columns_to_check:
                if col not in row:
                    continue
                    
                cell_value = row.get(col)
                if cell_value is None:
                    continue
                
                cell_str = str(cell_value)
                cell_lower = cell_str.lower()
                
                # Calculate similarity
                similarity = SequenceMatcher(
                    None, search_str, cell_lower
                ).ratio()
                
                if similarity > 0.4:  # Threshold for "similar"
                    if cell_str not in candidates or candidates[cell_str] < similarity:
                        candidates[cell_str] = similarity
        
        # Sort by similarity and return top matches
        sorted_candidates = sorted(
            candidates.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [c[0] for c in sorted_candidates[:5]]
    
    def _format_row(
        self,
        row: dict[str, Any],
        headers: list[str]
    ) -> dict[str, Any]:
        """
        Format a row preserving original data formatting.
        
        Implements Requirement 8.5: Preserve original data formatting.
        
        Args:
            row: Row to format.
            headers: Column headers.
            
        Returns:
            Formatted row.
        """
        formatted = {}
        
        for header in headers:
            value = row.get(header)
            formatted[header] = self._format_value(value)
        
        return formatted
    
    def _format_value(self, value: Any) -> Any:
        """
        Format a single value preserving original formatting.
        
        Preserves dates, currency, percentages, and other formats.
        
        Args:
            value: Value to format.
            
        Returns:
            Formatted value.
        """
        if value is None:
            return None
        
        # If already a string with formatting, preserve it
        if isinstance(value, str):
            return value
        
        # Handle datetime
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        
        # Handle floats that might be currency or percentages
        if isinstance(value, float):
            # Check if it's a whole number
            if value == int(value):
                return int(value)
            # Otherwise return with reasonable precision
            return round(value, 6)
        
        return value
