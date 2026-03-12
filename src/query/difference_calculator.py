"""
Difference Calculator for computing differences and trends across aligned data.

This module provides the DifferenceCalculator class that calculates absolute
differences, percentage changes, trends, and aggregates for comparison queries.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from enum import Enum

from src.models.domain_models import AlignedData

logger = logging.getLogger(__name__)


class TrendDirection(str, Enum):
    """Trend direction for numerical comparisons."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"


class DifferenceCalculator:
    """
    Calculates differences and trends across aligned data.
    
    This class handles absolute differences, percentage changes, trend detection,
    and aggregate calculations for numerical data.
    """
    
    def __init__(
        self,
        stable_threshold: float = 0.05,  # ±5% for stable trend
        min_value_for_percentage: float = 0.01  # Minimum value to calculate percentage
    ):
        """
        Initialize the DifferenceCalculator.
        
        Args:
            stable_threshold: Threshold for considering a trend stable (default ±5%)
            min_value_for_percentage: Minimum value to avoid division by very small numbers
        """
        self.stable_threshold = stable_threshold
        self.min_value_for_percentage = min_value_for_percentage
        
        logger.info("DifferenceCalculator initialized")
    
    def calculate_differences(self, aligned_data: AlignedData) -> Dict[str, Any]:
        """
        Calculate differences across aligned data.
        
        Args:
            aligned_data: Aligned data structure with common columns and file data
        
        Returns:
            Dictionary containing differences, trends, and aggregates
        """
        if not aligned_data.file_data or not aligned_data.common_columns:
            logger.warning("No data available for difference calculation")
            return {}
        
        logger.info(f"Calculating differences for {len(aligned_data.common_columns)} columns")
        
        results = {
            "column_differences": {},
            "aggregates": {},
            "trends": {},
            "summary_stats": {}
        }
        
        # Calculate differences for each common column
        for column in aligned_data.common_columns:
            column_results = self._calculate_column_differences(
                aligned_data,
                column
            )
            
            if column_results:
                results["column_differences"][column] = column_results
        
        # Calculate aggregates across all files
        results["aggregates"] = self._calculate_aggregates(aligned_data)
        
        # Detect trends
        results["trends"] = self._detect_trends(results["column_differences"])
        
        # Calculate summary statistics
        results["summary_stats"] = self._calculate_summary_stats(aligned_data)
        
        logger.info(f"Calculated differences for {len(results['column_differences'])} columns")
        
        return results
    
    def _calculate_column_differences(
        self,
        aligned_data: AlignedData,
        column: str
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate differences for a specific column across files.
        
        Args:
            aligned_data: Aligned data structure
            column: Column name to analyze
        
        Returns:
            Dictionary with difference calculations or None if not numerical
        """
        # Extract values for this column from all files
        file_values = {}
        
        for file_id, rows in aligned_data.file_data.items():
            values = []
            for row in rows:
                value = row.get(column)
                if value is not None:
                    values.append(value)
            
            if values:
                file_values[file_id] = values
        
        if not file_values:
            return None
        
        # Check if values are numerical
        if not self._is_numerical_column(file_values):
            return None
        
        # Calculate pairwise differences between files
        file_ids = list(file_values.keys())
        differences = {}
        
        for i in range(len(file_ids) - 1):
            file1 = file_ids[i]
            file2 = file_ids[i + 1]
            
            diff_key = f"{file1}_vs_{file2}"
            differences[diff_key] = self._calculate_pairwise_difference(
                file_values[file1],
                file_values[file2]
            )
        
        return differences
    
    def _is_numerical_column(self, file_values: Dict[str, List[Any]]) -> bool:
        """
        Check if a column contains numerical data.
        
        Args:
            file_values: Dictionary mapping file_id to list of values
        
        Returns:
            True if column is numerical
        """
        for values in file_values.values():
            for value in values:
                if value is not None:
                    try:
                        float(value)
                        return True
                    except (ValueError, TypeError):
                        return False
        
        return False
    
    def _calculate_pairwise_difference(
        self,
        values1: List[Any],
        values2: List[Any]
    ) -> Dict[str, Any]:
        """
        Calculate differences between two sets of values.
        
        Args:
            values1: Values from first file
            values2: Values from second file
        
        Returns:
            Dictionary with absolute and percentage differences
        """
        # Convert to numerical values
        nums1 = self._to_numbers(values1)
        nums2 = self._to_numbers(values2)
        
        if not nums1 or not nums2:
            return {
                "absolute_difference": None,
                "percentage_change": None,
                "trend": None,
                "missing_data": True
            }
        
        # Calculate averages for comparison
        avg1 = sum(nums1) / len(nums1)
        avg2 = sum(nums2) / len(nums2)
        
        # Absolute difference
        absolute_diff = avg2 - avg1
        
        # Percentage change (with division-by-zero handling)
        percentage_change = self._calculate_percentage_change(avg1, avg2)
        
        # Trend detection
        trend = self._determine_trend(percentage_change)
        
        return {
            "absolute_difference": round(absolute_diff, 2),
            "percentage_change": percentage_change,
            "trend": trend,
            "value1_avg": round(avg1, 2),
            "value2_avg": round(avg2, 2),
            "missing_data": False
        }
    
    def _to_numbers(self, values: List[Any]) -> List[float]:
        """
        Convert values to numbers, filtering out non-numerical values.
        
        Args:
            values: List of values to convert
        
        Returns:
            List of numerical values
        """
        numbers = []
        
        for value in values:
            if value is not None:
                try:
                    num = float(value)
                    numbers.append(num)
                except (ValueError, TypeError):
                    continue
        
        return numbers
    
    def _calculate_percentage_change(
        self,
        value1: float,
        value2: float
    ) -> Optional[float]:
        """
        Calculate percentage change with division-by-zero handling.
        
        Args:
            value1: Original value
            value2: New value
        
        Returns:
            Percentage change or None if calculation not possible
        """
        # Handle division by zero or very small numbers
        if abs(value1) < self.min_value_for_percentage:
            if abs(value2) < self.min_value_for_percentage:
                return 0.0  # Both values are essentially zero
            else:
                return None  # Cannot calculate meaningful percentage
        
        percentage = ((value2 - value1) / abs(value1)) * 100
        return round(percentage, 2)
    
    def _determine_trend(self, percentage_change: Optional[float]) -> str:
        """
        Determine trend direction based on percentage change.
        
        Args:
            percentage_change: Percentage change value
        
        Returns:
            Trend direction (increasing, decreasing, stable)
        """
        if percentage_change is None:
            return "unknown"
        
        threshold_percentage = self.stable_threshold * 100
        
        if percentage_change > threshold_percentage:
            return TrendDirection.INCREASING
        elif percentage_change < -threshold_percentage:
            return TrendDirection.DECREASING
        else:
            return TrendDirection.STABLE
    
    def _calculate_aggregates(self, aligned_data: AlignedData) -> Dict[str, Any]:
        """
        Calculate aggregate statistics across all files.
        
        Args:
            aligned_data: Aligned data structure
        
        Returns:
            Dictionary with aggregate statistics
        """
        aggregates = {}
        
        for column in aligned_data.common_columns:
            # Collect all numerical values for this column
            all_values = []
            
            for file_id, rows in aligned_data.file_data.items():
                for row in rows:
                    value = row.get(column)
                    if value is not None:
                        try:
                            num = float(value)
                            all_values.append(num)
                        except (ValueError, TypeError):
                            continue
            
            if all_values:
                aggregates[column] = {
                    "sum": round(sum(all_values), 2),
                    "average": round(sum(all_values) / len(all_values), 2),
                    "min": round(min(all_values), 2),
                    "max": round(max(all_values), 2),
                    "count": len(all_values)
                }
        
        return aggregates
    
    def _detect_trends(
        self,
        column_differences: Dict[str, Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Detect overall trends for each column.
        
        Args:
            column_differences: Column-wise difference calculations
        
        Returns:
            Dictionary mapping column to overall trend
        """
        trends = {}
        
        for column, differences in column_differences.items():
            # Collect all trends for this column
            column_trends = []
            
            for diff_key, diff_data in differences.items():
                if isinstance(diff_data, dict) and "trend" in diff_data:
                    trend = diff_data["trend"]
                    if trend != "unknown":
                        column_trends.append(trend)
            
            # Determine overall trend (most common)
            if column_trends:
                # Count occurrences
                trend_counts = {}
                for trend in column_trends:
                    trend_counts[trend] = trend_counts.get(trend, 0) + 1
                
                # Get most common trend
                overall_trend = max(trend_counts, key=trend_counts.get)
                trends[column] = overall_trend
        
        return trends
    
    def _calculate_summary_stats(self, aligned_data: AlignedData) -> Dict[str, Any]:
        """
        Calculate summary statistics for the comparison.
        
        Args:
            aligned_data: Aligned data structure
        
        Returns:
            Dictionary with summary statistics
        """
        total_rows = sum(
            len(rows) for rows in aligned_data.file_data.values()
        )
        
        return {
            "total_files": len(aligned_data.file_data),
            "total_columns": len(aligned_data.common_columns),
            "total_rows": total_rows,
            "files_with_missing_columns": len(aligned_data.missing_columns)
        }
