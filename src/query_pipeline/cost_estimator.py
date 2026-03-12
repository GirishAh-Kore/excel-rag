"""
Query cost estimation for the Excel query pipeline.

This module provides cost estimation capabilities for queries, allowing
the system to estimate resource usage before execution and reject
expensive queries that exceed configured limits.

Supports Requirements:
- 42.1: Estimate cost based on files to scan, rows to process, complexity
- 42.2: Support cost limits that reject expensive queries
- 42.3: Suggest ways to reduce query scope when rejected
- 42.5: Track query cost statistics
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol

from src.exceptions import QueryError
from src.models.query_pipeline import QueryType


logger = logging.getLogger(__name__)


# =============================================================================
# Constants and Configuration
# =============================================================================

# Default cost weights
DEFAULT_FILE_SCAN_COST = 10.0
DEFAULT_ROW_PROCESS_COST = 0.001
DEFAULT_COMPLEXITY_MULTIPLIER = 1.5
DEFAULT_AGGREGATION_COST = 5.0
DEFAULT_COMPARISON_COST = 20.0
DEFAULT_SUMMARIZATION_COST = 15.0
DEFAULT_LOOKUP_COST = 2.0

# Default limits
DEFAULT_MAX_COST = 1000.0
DEFAULT_WARNING_THRESHOLD = 0.7  # 70% of max cost


class CostLevel(str, Enum):
    """Cost level classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXCESSIVE = "excessive"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class CostWeights:
    """
    Weights for cost calculation components.
    
    Attributes:
        file_scan_cost: Base cost per file to scan.
        row_process_cost: Cost per row to process.
        complexity_multiplier: Multiplier for complex queries.
        aggregation_cost: Additional cost for aggregation queries.
        comparison_cost: Additional cost for comparison queries.
        summarization_cost: Additional cost for summarization queries.
        lookup_cost: Additional cost for lookup queries.
    """
    file_scan_cost: float = DEFAULT_FILE_SCAN_COST
    row_process_cost: float = DEFAULT_ROW_PROCESS_COST
    complexity_multiplier: float = DEFAULT_COMPLEXITY_MULTIPLIER
    aggregation_cost: float = DEFAULT_AGGREGATION_COST
    comparison_cost: float = DEFAULT_COMPARISON_COST
    summarization_cost: float = DEFAULT_SUMMARIZATION_COST
    lookup_cost: float = DEFAULT_LOOKUP_COST
    
    def __post_init__(self) -> None:
        """Validate weight values."""
        for field_name in [
            "file_scan_cost", "row_process_cost", "complexity_multiplier",
            "aggregation_cost", "comparison_cost", "summarization_cost",
            "lookup_cost"
        ]:
            value = getattr(self, field_name)
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative, got {value}")


@dataclass
class CostLimits:
    """
    Cost limits for query execution.
    
    Attributes:
        max_cost: Maximum allowed cost before rejection.
        warning_threshold: Threshold (0-1) for warning about high cost.
        max_files: Maximum number of files to scan.
        max_rows: Maximum number of rows to process.
    """
    max_cost: float = DEFAULT_MAX_COST
    warning_threshold: float = DEFAULT_WARNING_THRESHOLD
    max_files: Optional[int] = None
    max_rows: Optional[int] = None
    
    def __post_init__(self) -> None:
        """Validate limit values."""
        if self.max_cost <= 0:
            raise ValueError(f"max_cost must be positive, got {self.max_cost}")
        if not 0 < self.warning_threshold <= 1:
            raise ValueError(
                f"warning_threshold must be between 0 and 1, got {self.warning_threshold}"
            )


@dataclass
class QueryCostBreakdown:
    """
    Detailed breakdown of query cost components.
    
    Attributes:
        file_scan_cost: Cost from scanning files.
        row_processing_cost: Cost from processing rows.
        query_type_cost: Cost from query type complexity.
        complexity_cost: Additional cost from query complexity.
        total_cost: Total estimated cost.
    """
    file_scan_cost: float
    row_processing_cost: float
    query_type_cost: float
    complexity_cost: float
    total_cost: float
    
    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "file_scan_cost": self.file_scan_cost,
            "row_processing_cost": self.row_processing_cost,
            "query_type_cost": self.query_type_cost,
            "complexity_cost": self.complexity_cost,
            "total_cost": self.total_cost
        }


@dataclass
class CostEstimate:
    """
    Complete cost estimate for a query.
    
    Attributes:
        estimated_cost: Total estimated cost.
        cost_level: Classification of cost level.
        breakdown: Detailed cost breakdown.
        files_to_scan: Number of files to scan.
        rows_to_process: Estimated rows to process.
        query_type: Type of query.
        is_within_limits: Whether cost is within limits.
        exceeds_warning: Whether cost exceeds warning threshold.
        rejection_reason: Reason for rejection (if rejected).
        suggestions: Suggestions for reducing cost.
    """
    estimated_cost: float
    cost_level: CostLevel
    breakdown: QueryCostBreakdown
    files_to_scan: int
    rows_to_process: int
    query_type: Optional[QueryType]
    is_within_limits: bool
    exceeds_warning: bool
    rejection_reason: Optional[str] = None
    suggestions: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "estimated_cost": self.estimated_cost,
            "cost_level": self.cost_level.value,
            "breakdown": self.breakdown.to_dict(),
            "files_to_scan": self.files_to_scan,
            "rows_to_process": self.rows_to_process,
            "query_type": self.query_type.value if self.query_type else None,
            "is_within_limits": self.is_within_limits,
            "exceeds_warning": self.exceeds_warning,
            "rejection_reason": self.rejection_reason,
            "suggestions": self.suggestions
        }


@dataclass
class QueryCostStatistics:
    """
    Statistics about query costs over time.
    
    Attributes:
        total_queries: Total number of queries estimated.
        total_cost: Total cost of all queries.
        average_cost: Average cost per query.
        max_cost_seen: Maximum cost seen.
        rejected_count: Number of queries rejected.
        high_cost_count: Number of high-cost queries.
    """
    total_queries: int = 0
    total_cost: float = 0.0
    average_cost: float = 0.0
    max_cost_seen: float = 0.0
    rejected_count: int = 0
    high_cost_count: int = 0
    
    def record_estimate(self, estimate: CostEstimate) -> None:
        """
        Record a cost estimate in statistics.
        
        Args:
            estimate: The cost estimate to record.
        """
        self.total_queries += 1
        self.total_cost += estimate.estimated_cost
        self.average_cost = self.total_cost / self.total_queries
        self.max_cost_seen = max(self.max_cost_seen, estimate.estimated_cost)
        
        if not estimate.is_within_limits:
            self.rejected_count += 1
        
        if estimate.cost_level in (CostLevel.HIGH, CostLevel.EXCESSIVE):
            self.high_cost_count += 1


# =============================================================================
# Protocols
# =============================================================================

class FileMetadataProviderProtocol(Protocol):
    """Protocol for providing file metadata for cost estimation."""
    
    def get_file_row_count(self, file_id: str) -> int:
        """Get total row count for a file."""
        ...
    
    def get_total_indexed_rows(self) -> int:
        """Get total rows across all indexed files."""
        ...


# =============================================================================
# Query Cost Estimator
# =============================================================================

class QueryCostEstimator:
    """
    Estimates query execution cost and enforces limits.
    
    Calculates estimated cost based on files to scan, rows to process,
    and query complexity. Rejects queries that exceed configured limits
    and provides suggestions for reducing query scope.
    
    All dependencies are injected via constructor following DIP.
    
    Attributes:
        _weights: Cost calculation weights.
        _limits: Cost limits for rejection.
        _statistics: Running statistics about query costs.
        _logger: Logger instance.
    
    Example:
        >>> weights = CostWeights(file_scan_cost=10.0)
        >>> limits = CostLimits(max_cost=500.0)
        >>> estimator = QueryCostEstimator(weights, limits)
        >>> estimate = estimator.estimate_cost(
        ...     files_to_scan=5,
        ...     estimated_rows=50000,
        ...     query_type=QueryType.AGGREGATION
        ... )
        >>> if not estimate.is_within_limits:
        ...     print(estimate.suggestions)
    
    Supports Requirements 42.1, 42.2, 42.3, 42.5.
    """
    
    def __init__(
        self,
        weights: Optional[CostWeights] = None,
        limits: Optional[CostLimits] = None
    ) -> None:
        """
        Initialize the cost estimator.
        
        Args:
            weights: Cost calculation weights.
            limits: Cost limits for rejection.
        """
        self._weights = weights or CostWeights()
        self._limits = limits or CostLimits()
        self._statistics = QueryCostStatistics()
        self._logger = logging.getLogger(__name__)
    
    def estimate_cost(
        self,
        files_to_scan: int,
        estimated_rows: int,
        query_type: Optional[QueryType] = None,
        complexity_score: float = 1.0,
        has_filters: bool = False,
        has_aggregations: bool = False,
        is_comparison: bool = False
    ) -> CostEstimate:
        """
        Estimate the cost of executing a query.
        
        Calculates cost based on files, rows, query type, and complexity.
        Returns estimate with breakdown and limit checking.
        
        Args:
            files_to_scan: Number of files to scan.
            estimated_rows: Estimated number of rows to process.
            query_type: Type of query (if known).
            complexity_score: Query complexity score (1.0 = normal).
            has_filters: Whether query has filter conditions.
            has_aggregations: Whether query has aggregations.
            is_comparison: Whether query compares multiple sources.
            
        Returns:
            CostEstimate with full cost analysis.
        
        Supports Requirement 42.1: Estimate cost based on files, rows, complexity.
        """
        # Calculate component costs
        file_scan_cost = files_to_scan * self._weights.file_scan_cost
        row_processing_cost = estimated_rows * self._weights.row_process_cost
        
        # Calculate query type cost
        query_type_cost = self._calculate_query_type_cost(
            query_type, has_aggregations, is_comparison
        )
        
        # Calculate complexity cost
        complexity_cost = 0.0
        if complexity_score > 1.0:
            base_cost = file_scan_cost + row_processing_cost + query_type_cost
            complexity_cost = base_cost * (complexity_score - 1.0) * self._weights.complexity_multiplier
        
        # Filters can reduce cost slightly
        if has_filters:
            row_processing_cost *= 0.8  # 20% reduction with filters
        
        # Calculate total
        total_cost = (
            file_scan_cost
            + row_processing_cost
            + query_type_cost
            + complexity_cost
        )
        
        # Create breakdown
        breakdown = QueryCostBreakdown(
            file_scan_cost=file_scan_cost,
            row_processing_cost=row_processing_cost,
            query_type_cost=query_type_cost,
            complexity_cost=complexity_cost,
            total_cost=total_cost
        )
        
        # Determine cost level
        cost_level = self._classify_cost_level(total_cost)
        
        # Check limits
        is_within_limits, rejection_reason = self._check_limits(
            total_cost, files_to_scan, estimated_rows
        )
        
        # Check warning threshold
        exceeds_warning = total_cost > (self._limits.max_cost * self._limits.warning_threshold)
        
        # Generate suggestions if needed
        suggestions = []
        if not is_within_limits or exceeds_warning:
            suggestions = self._generate_suggestions(
                files_to_scan, estimated_rows, query_type, total_cost
            )
        
        estimate = CostEstimate(
            estimated_cost=total_cost,
            cost_level=cost_level,
            breakdown=breakdown,
            files_to_scan=files_to_scan,
            rows_to_process=estimated_rows,
            query_type=query_type,
            is_within_limits=is_within_limits,
            exceeds_warning=exceeds_warning,
            rejection_reason=rejection_reason,
            suggestions=suggestions
        )
        
        # Record statistics
        self._statistics.record_estimate(estimate)
        
        self._logger.debug(
            f"Cost estimate: {total_cost:.2f} "
            f"(files={files_to_scan}, rows={estimated_rows}, "
            f"type={query_type}, within_limits={is_within_limits})"
        )
        
        return estimate
    
    def check_and_reject(
        self,
        files_to_scan: int,
        estimated_rows: int,
        query_type: Optional[QueryType] = None,
        complexity_score: float = 1.0
    ) -> CostEstimate:
        """
        Estimate cost and raise exception if limits exceeded.
        
        Convenience method that estimates cost and raises QueryError
        if the query exceeds configured limits.
        
        Args:
            files_to_scan: Number of files to scan.
            estimated_rows: Estimated number of rows to process.
            query_type: Type of query (if known).
            complexity_score: Query complexity score.
            
        Returns:
            CostEstimate if within limits.
            
        Raises:
            QueryError: If query exceeds cost limits.
        
        Supports Requirement 42.2: Support cost limits that reject expensive queries.
        """
        estimate = self.estimate_cost(
            files_to_scan=files_to_scan,
            estimated_rows=estimated_rows,
            query_type=query_type,
            complexity_score=complexity_score
        )
        
        if not estimate.is_within_limits:
            suggestions_text = "\n".join(f"  - {s}" for s in estimate.suggestions)
            raise QueryError(
                f"Query exceeds cost limits: {estimate.rejection_reason}\n"
                f"Suggestions to reduce cost:\n{suggestions_text}",
                details={
                    "estimated_cost": estimate.estimated_cost,
                    "max_cost": self._limits.max_cost,
                    "files_to_scan": files_to_scan,
                    "estimated_rows": estimated_rows,
                    "suggestions": estimate.suggestions
                }
            )
        
        return estimate
    
    def get_statistics(self) -> QueryCostStatistics:
        """
        Get query cost statistics.
        
        Returns:
            QueryCostStatistics with accumulated data.
        
        Supports Requirement 42.5: Track query cost statistics.
        """
        return self._statistics
    
    def reset_statistics(self) -> None:
        """Reset query cost statistics."""
        self._statistics = QueryCostStatistics()
    
    def update_limits(self, limits: CostLimits) -> None:
        """
        Update cost limits.
        
        Args:
            limits: New cost limits to apply.
        """
        self._limits = limits
        self._logger.info(f"Updated cost limits: max_cost={limits.max_cost}")
    
    def _calculate_query_type_cost(
        self,
        query_type: Optional[QueryType],
        has_aggregations: bool,
        is_comparison: bool
    ) -> float:
        """Calculate cost based on query type."""
        if query_type == QueryType.COMPARISON or is_comparison:
            return self._weights.comparison_cost
        elif query_type == QueryType.SUMMARIZATION:
            return self._weights.summarization_cost
        elif query_type == QueryType.AGGREGATION or has_aggregations:
            return self._weights.aggregation_cost
        elif query_type == QueryType.LOOKUP:
            return self._weights.lookup_cost
        else:
            return 0.0
    
    def _classify_cost_level(self, cost: float) -> CostLevel:
        """Classify cost into a level."""
        max_cost = self._limits.max_cost
        
        if cost > max_cost:
            return CostLevel.EXCESSIVE
        elif cost > max_cost * 0.7:
            return CostLevel.HIGH
        elif cost > max_cost * 0.3:
            return CostLevel.MEDIUM
        else:
            return CostLevel.LOW
    
    def _check_limits(
        self,
        total_cost: float,
        files_to_scan: int,
        estimated_rows: int
    ) -> tuple[bool, Optional[str]]:
        """
        Check if query is within limits.
        
        Returns:
            Tuple of (is_within_limits, rejection_reason).
        """
        if total_cost > self._limits.max_cost:
            return False, f"Estimated cost ({total_cost:.2f}) exceeds maximum ({self._limits.max_cost:.2f})"
        
        if self._limits.max_files and files_to_scan > self._limits.max_files:
            return False, f"Files to scan ({files_to_scan}) exceeds maximum ({self._limits.max_files})"
        
        if self._limits.max_rows and estimated_rows > self._limits.max_rows:
            return False, f"Rows to process ({estimated_rows}) exceeds maximum ({self._limits.max_rows})"
        
        return True, None
    
    def _generate_suggestions(
        self,
        files_to_scan: int,
        estimated_rows: int,
        query_type: Optional[QueryType],
        total_cost: float
    ) -> list[str]:
        """
        Generate suggestions for reducing query cost.
        
        Args:
            files_to_scan: Number of files to scan.
            estimated_rows: Estimated rows to process.
            query_type: Type of query.
            total_cost: Total estimated cost.
            
        Returns:
            List of suggestions for reducing cost.
        
        Supports Requirement 42.3: Suggest ways to reduce query scope.
        """
        suggestions: list[str] = []
        
        # File-related suggestions
        if files_to_scan > 3:
            suggestions.append(
                f"Specify a particular file to reduce from {files_to_scan} files to 1"
            )
        
        # Row-related suggestions
        if estimated_rows > 10000:
            suggestions.append(
                "Add filter conditions to reduce the number of rows processed"
            )
            suggestions.append(
                "Specify a particular sheet to narrow the data scope"
            )
        
        # Query type suggestions
        if query_type == QueryType.COMPARISON:
            suggestions.append(
                "Compare fewer files or time periods to reduce complexity"
            )
        elif query_type == QueryType.SUMMARIZATION:
            suggestions.append(
                "Request a summary of a specific sheet instead of the entire file"
            )
        
        # General suggestions
        if total_cost > self._limits.max_cost * 0.8:
            suggestions.append(
                "Consider breaking the query into smaller, more focused questions"
            )
        
        # Time-based suggestions
        if estimated_rows > 50000:
            suggestions.append(
                "Add a date range filter to limit the data to a specific period"
            )
        
        return suggestions


# =============================================================================
# Cost-Aware Query Decorator
# =============================================================================

class CostAwareQueryError(QueryError):
    """
    Query error with cost information.
    
    Raised when a query is rejected due to cost limits, includes
    the cost estimate and suggestions.
    """
    
    def __init__(
        self,
        message: str,
        estimate: CostEstimate,
        details: Optional[dict] = None
    ) -> None:
        """
        Initialize the error.
        
        Args:
            message: Error message.
            estimate: The cost estimate that caused rejection.
            details: Additional error details.
        """
        super().__init__(message, details)
        self.estimate = estimate


# =============================================================================
# Factory Function
# =============================================================================

def create_cost_estimator(
    max_cost: float = DEFAULT_MAX_COST,
    file_scan_cost: float = DEFAULT_FILE_SCAN_COST,
    row_process_cost: float = DEFAULT_ROW_PROCESS_COST
) -> QueryCostEstimator:
    """
    Create a configured cost estimator.
    
    Factory function for creating QueryCostEstimator with common
    configuration options.
    
    Args:
        max_cost: Maximum allowed query cost.
        file_scan_cost: Cost per file to scan.
        row_process_cost: Cost per row to process.
        
    Returns:
        Configured QueryCostEstimator instance.
    """
    weights = CostWeights(
        file_scan_cost=file_scan_cost,
        row_process_cost=row_process_cost
    )
    
    limits = CostLimits(max_cost=max_cost)
    
    return QueryCostEstimator(weights, limits)
