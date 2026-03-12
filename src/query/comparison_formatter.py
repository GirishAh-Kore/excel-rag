"""
Comparison Formatter for formatting comparison results.

This module provides the ComparisonFormatter class that generates natural language
summaries, creates visualization data, and formats comparison results.
"""

import logging
from typing import Dict, Any, List, Optional
import json

from src.models.domain_models import ComparisonResult, AlignedData
from src.abstractions.llm_service import LLMService
from src.abstractions.cache_service import CacheService

logger = logging.getLogger(__name__)


class ComparisonFormatter:
    """
    Formats comparison results for presentation.
    
    This class generates natural language summaries, creates structured data
    for visualization, and cites sources for compared values.
    """
    
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        cache_service: Optional[CacheService] = None,
        cache_ttl: int = 300  # 5 minutes
    ):
        """
        Initialize the ComparisonFormatter.
        
        Args:
            llm_service: Optional LLM service for generating summaries
            cache_service: Optional cache service for caching aligned data
            cache_ttl: Cache time-to-live in seconds (default 5 minutes)
        """
        self.llm_service = llm_service
        self.cache_service = cache_service
        self.cache_ttl = cache_ttl
        
        logger.info("ComparisonFormatter initialized")
    
    def format_comparison(
        self,
        file_ids: List[str],
        aligned_data: AlignedData,
        differences: Dict[str, Any],
        query: str
    ) -> ComparisonResult:
        """
        Format comparison results into a ComparisonResult object.
        
        Args:
            file_ids: List of file IDs compared
            aligned_data: Aligned data structure
            differences: Calculated differences
            query: Original user query
        
        Returns:
            Formatted ComparisonResult
        """
        logger.info(f"Formatting comparison results for {len(file_ids)} files")
        
        # Generate natural language summary
        summary = self._generate_summary(
            file_ids,
            aligned_data,
            differences,
            query
        )
        
        # Create visualization data
        visualization_data = self._create_visualization_data(
            aligned_data,
            differences
        )
        
        # Cache aligned data for follow-up questions
        if self.cache_service:
            self._cache_aligned_data(file_ids, aligned_data)
        
        # Create sources with citations
        aligned_data_dict = self._format_aligned_data(aligned_data)
        
        return ComparisonResult(
            files_compared=file_ids,
            aligned_data=aligned_data_dict,
            differences=differences,
            summary=summary,
            visualization_data=visualization_data
        )
    
    def _generate_summary(
        self,
        file_ids: List[str],
        aligned_data: AlignedData,
        differences: Dict[str, Any],
        query: str
    ) -> str:
        """
        Generate natural language summary of comparison.
        
        Args:
            file_ids: List of file IDs
            aligned_data: Aligned data structure
            differences: Calculated differences
            query: Original query
        
        Returns:
            Natural language summary
        """
        # If LLM service is available, use it to generate summary
        if self.llm_service:
            try:
                return self._generate_llm_summary(
                    file_ids,
                    aligned_data,
                    differences,
                    query
                )
            except Exception as e:
                logger.warning(f"Failed to generate LLM summary: {str(e)}")
                # Fall back to template-based summary
        
        # Template-based summary
        return self._generate_template_summary(
            file_ids,
            aligned_data,
            differences
        )
    
    def _generate_llm_summary(
        self,
        file_ids: List[str],
        aligned_data: AlignedData,
        differences: Dict[str, Any],
        query: str
    ) -> str:
        """
        Generate summary using LLM service.
        
        Args:
            file_ids: List of file IDs
            aligned_data: Aligned data structure
            differences: Calculated differences
            query: Original query
        
        Returns:
            LLM-generated summary
        """
        # Prepare context for LLM
        context = {
            "files_compared": len(file_ids),
            "common_columns": aligned_data.common_columns,
            "key_differences": self._extract_key_differences(differences),
            "trends": differences.get("trends", {}),
            "summary_stats": differences.get("summary_stats", {})
        }
        
        prompt = f"""
You are analyzing a comparison of {len(file_ids)} Excel files based on this query: "{query}"

Comparison Context:
{json.dumps(context, indent=2)}

Generate a concise natural language summary (2-3 sentences) highlighting:
1. The key findings from the comparison
2. Notable trends (increasing, decreasing, stable)
3. Any significant differences or patterns

Summary:
"""
        
        system_prompt = "You are a data analyst providing clear, concise summaries of data comparisons."
        
        summary = self.llm_service.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=200
        )
        
        return summary.strip()
    
    def _generate_template_summary(
        self,
        file_ids: List[str],
        aligned_data: AlignedData,
        differences: Dict[str, Any]
    ) -> str:
        """
        Generate summary using templates (fallback when LLM not available).
        
        Args:
            file_ids: List of file IDs
            aligned_data: Aligned data structure
            differences: Calculated differences
        
        Returns:
            Template-based summary
        """
        summary_parts = []
        
        # Basic comparison info
        summary_parts.append(
            f"Compared {len(file_ids)} files with {len(aligned_data.common_columns)} common columns."
        )
        
        # Highlight key trends
        trends = differences.get("trends", {})
        if trends:
            increasing = [col for col, trend in trends.items() if trend == "increasing"]
            decreasing = [col for col, trend in trends.items() if trend == "decreasing"]
            
            if increasing:
                summary_parts.append(
                    f"Increasing trends in: {', '.join(increasing[:3])}."
                )
            
            if decreasing:
                summary_parts.append(
                    f"Decreasing trends in: {', '.join(decreasing[:3])}."
                )
        
        # Note missing columns if any
        if aligned_data.missing_columns:
            summary_parts.append(
                f"Note: {len(aligned_data.missing_columns)} files have missing columns."
            )
        
        return " ".join(summary_parts)
    
    def _extract_key_differences(self, differences: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract the most significant differences for summary.
        
        Args:
            differences: Full differences dictionary
        
        Returns:
            Dictionary with key differences
        """
        key_diffs = {}
        
        column_diffs = differences.get("column_differences", {})
        
        for column, diffs in column_diffs.items():
            # Find the largest absolute or percentage change
            max_change = None
            max_change_value = 0
            
            for diff_key, diff_data in diffs.items():
                if isinstance(diff_data, dict):
                    abs_diff = diff_data.get("absolute_difference")
                    pct_change = diff_data.get("percentage_change")
                    
                    if abs_diff is not None and abs(abs_diff) > max_change_value:
                        max_change_value = abs(abs_diff)
                        max_change = {
                            "type": "absolute",
                            "value": abs_diff,
                            "percentage": pct_change,
                            "trend": diff_data.get("trend")
                        }
            
            if max_change:
                key_diffs[column] = max_change
        
        # Return top 5 by magnitude
        sorted_diffs = sorted(
            key_diffs.items(),
            key=lambda x: abs(x[1].get("value", 0)),
            reverse=True
        )
        
        return dict(sorted_diffs[:5])
    
    def _create_visualization_data(
        self,
        aligned_data: AlignedData,
        differences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create structured data for visualization.
        
        Args:
            aligned_data: Aligned data structure
            differences: Calculated differences
        
        Returns:
            Dictionary with visualization-ready data
        """
        viz_data = {
            "comparison_table": self._create_comparison_table(aligned_data),
            "trend_data": differences.get("trends", {}),
            "aggregates": differences.get("aggregates", {}),
            "summary_stats": differences.get("summary_stats", {})
        }
        
        return viz_data
    
    def _create_comparison_table(self, aligned_data: AlignedData) -> List[Dict[str, Any]]:
        """
        Create a comparison table from aligned data.
        
        Args:
            aligned_data: Aligned data structure
        
        Returns:
            List of row dictionaries for table display
        """
        table = []
        
        # Get maximum number of rows across all files
        max_rows = max(
            len(rows) for rows in aligned_data.file_data.values()
        ) if aligned_data.file_data else 0
        
        # Create rows for the table
        for i in range(min(max_rows, 10)):  # Limit to first 10 rows
            row = {"row_index": i}
            
            for file_id, rows in aligned_data.file_data.items():
                if i < len(rows):
                    # Add data from this file
                    for col in aligned_data.common_columns:
                        key = f"{file_id}_{col}"
                        row[key] = rows[i].get(col)
            
            table.append(row)
        
        return table
    
    def _format_aligned_data(self, aligned_data: AlignedData) -> Dict[str, Any]:
        """
        Format aligned data for inclusion in result.
        
        Args:
            aligned_data: Aligned data structure
        
        Returns:
            Dictionary representation of aligned data
        """
        return {
            "common_columns": aligned_data.common_columns,
            "file_data": aligned_data.file_data,
            "missing_columns": aligned_data.missing_columns
        }
    
    def _cache_aligned_data(
        self,
        file_ids: List[str],
        aligned_data: AlignedData
    ) -> None:
        """
        Cache aligned data for follow-up questions.
        
        Args:
            file_ids: List of file IDs
            aligned_data: Aligned data to cache
        """
        try:
            # Create cache key from file IDs
            cache_key = f"comparison_aligned_data:{':'.join(sorted(file_ids))}"
            
            # Serialize aligned data
            cache_value = {
                "common_columns": aligned_data.common_columns,
                "file_data": aligned_data.file_data,
                "missing_columns": aligned_data.missing_columns
            }
            
            # Store in cache with TTL
            self.cache_service.set(
                cache_key,
                json.dumps(cache_value),
                ttl=self.cache_ttl
            )
            
            logger.info(f"Cached aligned data for {len(file_ids)} files")
            
        except Exception as e:
            logger.warning(f"Failed to cache aligned data: {str(e)}")
    
    def get_cached_aligned_data(self, file_ids: List[str]) -> Optional[AlignedData]:
        """
        Retrieve cached aligned data for follow-up questions.
        
        Args:
            file_ids: List of file IDs
        
        Returns:
            AlignedData if found in cache, None otherwise
        """
        if not self.cache_service:
            return None
        
        try:
            cache_key = f"comparison_aligned_data:{':'.join(sorted(file_ids))}"
            cached_value = self.cache_service.get(cache_key)
            
            if cached_value:
                data = json.loads(cached_value)
                return AlignedData(
                    common_columns=data["common_columns"],
                    file_data=data["file_data"],
                    missing_columns=data["missing_columns"]
                )
            
        except Exception as e:
            logger.warning(f"Failed to retrieve cached aligned data: {str(e)}")
        
        return None
