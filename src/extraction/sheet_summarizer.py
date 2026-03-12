"""
LLM-based sheet summarization for improved disambiguation.

This module provides functionality to generate semantic summaries of Excel sheets
using LLMs, which helps with sheet selection when multiple candidates match a query.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.abstractions.llm_service import LLMService
from src.abstractions.llm_service_factory import LLMServiceFactory
from src.extraction.extraction_strategy import ExtractionConfig
from src.models.domain_models import SheetData


logger = logging.getLogger(__name__)


class SheetSummarizer:
    """
    Generate LLM-based summaries for Excel sheets.
    
    Provides semantic understanding of sheet purpose and content,
    which improves sheet selection and disambiguation.
    """
    
    def __init__(self, config: ExtractionConfig, llm_service: Optional[LLMService] = None):
        """
        Initialize the sheet summarizer.
        
        Args:
            config: Extraction configuration
            llm_service: Optional LLM service (will create if not provided)
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize LLM service
        if llm_service:
            self.llm = llm_service
        elif config.enable_llm_summarization:
            self.llm = LLMServiceFactory.create(
                provider=config.summarization_provider,
                model=config.summarization_model
            )
        else:
            self.llm = None
    
    async def generate_sheet_summary(
        self,
        sheet_data: SheetData,
        file_name: str,
        include_sample_data: bool = True
    ) -> Optional[str]:
        """
        Generate a semantic summary of a sheet's purpose and content.
        
        Args:
            sheet_data: Sheet data to summarize
            file_name: Name of the file containing the sheet
            include_sample_data: Whether to include sample rows in prompt
            
        Returns:
            LLM-generated summary or None if summarization is disabled
        """
        if not self.config.enable_llm_summarization or not self.llm:
            return None
        
        try:
            prompt = self._build_summary_prompt(sheet_data, file_name, include_sample_data)
            
            summary = await self.llm.generate(
                prompt=prompt,
                max_tokens=self.config.summarization_max_tokens,
                temperature=0.3  # Lower temperature for more consistent summaries
            )
            
            self.logger.info(
                f"Generated summary for sheet '{sheet_data.sheet_name}' "
                f"in file '{file_name}'"
            )
            
            return summary.strip()
            
        except Exception as e:
            self.logger.error(
                f"Failed to generate summary for sheet '{sheet_data.sheet_name}': {e}"
            )
            return None
    
    def _build_summary_prompt(
        self,
        sheet_data: SheetData,
        file_name: str,
        include_sample_data: bool
    ) -> str:
        """Build the prompt for sheet summarization."""
        
        prompt_parts = [
            "Analyze this Excel sheet and provide a concise 2-3 sentence summary of its purpose and content.",
            "Focus on what the sheet is used for and what kind of information it contains.",
            "",
            f"File: {file_name}",
            f"Sheet: {sheet_data.sheet_name}",
            f"Columns ({len(sheet_data.headers)}): {', '.join(sheet_data.headers[:15])}",
        ]
        
        if len(sheet_data.headers) > 15:
            prompt_parts.append(f"... and {len(sheet_data.headers) - 15} more columns")
        
        prompt_parts.append(f"Row Count: {sheet_data.row_count}")
        
        # Add data type information
        data_info = []
        if sheet_data.has_numbers:
            data_info.append("numerical data")
        if sheet_data.has_dates:
            data_info.append("dates")
        if sheet_data.has_pivot_tables:
            data_info.append(f"{len(sheet_data.pivot_tables)} pivot tables")
        if sheet_data.has_charts:
            data_info.append(f"{len(sheet_data.charts)} charts")
        
        if data_info:
            prompt_parts.append(f"Contains: {', '.join(data_info)}")
        
        # Add sample data if requested
        if include_sample_data and sheet_data.rows:
            prompt_parts.append("\nSample Data (first 3 rows):")
            for idx, row in enumerate(sheet_data.rows[:3], start=1):
                row_str = self._format_row_for_prompt(row)
                if row_str:
                    prompt_parts.append(f"Row {idx}: {row_str}")
        
        prompt_parts.append("\nSummary:")
        
        return "\n".join(prompt_parts)
    
    def _format_row_for_prompt(self, row: Dict[str, Any], max_length: int = 200) -> str:
        """Format a row for inclusion in the prompt."""
        parts = []
        for key, value in row.items():
            if value is not None and value != "":
                # Format value appropriately
                if isinstance(value, datetime):
                    value_str = value.strftime("%Y-%m-%d")
                elif isinstance(value, float):
                    value_str = f"{value:.2f}"
                else:
                    value_str = str(value)[:50]  # Limit individual values
                
                parts.append(f"{key}: {value_str}")
        
        result = ", ".join(parts)
        if len(result) > max_length:
            result = result[:max_length] + "..."
        
        return result
    
    async def rank_sheets_for_query(
        self,
        query: str,
        candidate_sheets: List[Tuple[SheetData, str]],  # (sheet, file_name)
        use_llm_ranking: bool = True
    ) -> List[Tuple[SheetData, float, str]]:
        """
        Rank sheets based on relevance to a query.
        
        Args:
            query: User query
            candidate_sheets: List of (SheetData, file_name) tuples
            use_llm_ranking: Whether to use LLM for ranking (vs just summaries)
            
        Returns:
            List of (SheetData, relevance_score, summary) tuples, sorted by relevance
        """
        if not self.llm:
            # Return with default scores if LLM not available
            return [(sheet, 0.5, sheet.summary) for sheet, _ in candidate_sheets]
        
        results = []
        
        for sheet_data, file_name in candidate_sheets:
            try:
                # Get or generate summary
                summary = sheet_data.llm_summary
                if not summary:
                    summary = await self.generate_sheet_summary(sheet_data, file_name)
                    if not summary:
                        summary = sheet_data.summary  # Fall back to basic summary
                
                # Optionally use LLM to score relevance
                if use_llm_ranking:
                    score = await self._score_sheet_relevance(query, sheet_data, summary)
                else:
                    score = 0.5  # Neutral score
                
                results.append((sheet_data, score, summary))
                
            except Exception as e:
                self.logger.error(
                    f"Failed to rank sheet '{sheet_data.sheet_name}': {e}"
                )
                results.append((sheet_data, 0.0, sheet_data.summary))
        
        # Sort by relevance score (descending)
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    async def _score_sheet_relevance(
        self,
        query: str,
        sheet_data: SheetData,
        summary: str
    ) -> float:
        """
        Use LLM to score how relevant a sheet is to a query.
        
        Args:
            query: User query
            sheet_data: Sheet data
            summary: Sheet summary
            
        Returns:
            Relevance score between 0.0 and 1.0
        """
        try:
            prompt = f"""Rate how relevant this Excel sheet is to the user's query on a scale of 0-10.

User Query: {query}

Sheet Information:
- Name: {sheet_data.sheet_name}
- Columns: {', '.join(sheet_data.headers[:10])}
- Summary: {summary}

Provide only a number between 0 and 10, where:
- 0 = Not relevant at all
- 5 = Somewhat relevant
- 10 = Highly relevant

Relevance Score:"""
            
            response = await self.llm.generate(
                prompt=prompt,
                max_tokens=10,
                temperature=0.1
            )
            
            # Parse score
            score_text = response.strip()
            # Extract first number found
            import re
            match = re.search(r'\d+\.?\d*', score_text)
            if match:
                score = float(match.group())
                # Normalize to 0-1 range
                return min(max(score / 10.0, 0.0), 1.0)
            
            return 0.5  # Default if parsing fails
            
        except Exception as e:
            self.logger.error(f"Failed to score sheet relevance: {e}")
            return 0.5
    
    async def generate_disambiguation_prompt(
        self,
        query: str,
        ranked_sheets: List[Tuple[SheetData, float, str]],
        file_name: str
    ) -> str:
        """
        Generate a user-friendly prompt for manual sheet selection.
        
        Args:
            query: User query
            ranked_sheets: Ranked sheets with scores and summaries
            file_name: File name
            
        Returns:
            Formatted prompt for user
        """
        prompt_parts = [
            f"Multiple sheets in '{file_name}' match your query: \"{query}\"",
            "",
            "Please select the most relevant sheet:",
            ""
        ]
        
        for idx, (sheet, score, summary) in enumerate(ranked_sheets[:5], start=1):
            prompt_parts.append(f"{idx}. {sheet.sheet_name}")
            prompt_parts.append(f"   {summary}")
            prompt_parts.append(f"   Columns: {', '.join(sheet.headers[:5])}")
            if len(sheet.headers) > 5:
                prompt_parts.append(f"   ... and {len(sheet.headers) - 5} more")
            prompt_parts.append(f"   Rows: {sheet.row_count}")
            prompt_parts.append("")
        
        return "\n".join(prompt_parts)
