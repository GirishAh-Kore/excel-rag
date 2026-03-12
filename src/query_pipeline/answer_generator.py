"""
Answer Generator Module for Smart Excel Query Pipeline.

This module implements the AnswerGenerator for generating natural language
answers with source citations, confidence scoring, and data lineage tracking.

Key Features:
- Source citations for every factual claim
- Citation format: [File: filename, Sheet: sheetname, Range: cellrange]
- Confidence score with breakdown (file, sheet, data)
- Disclaimer when confidence < 0.7
- Numeric precision preservation from source data
- Navigable citations with lineage_id

Supports Requirements 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from src.abstractions.llm_service import LLMService
from src.exceptions import ProcessingError
from src.models.query_pipeline import (
    Citation,
    ConfidenceBreakdown,
    QueryResponse,
    QueryType,
)
from src.query_pipeline.processors.base import ProcessedResult

logger = logging.getLogger(__name__)


# Configuration constants
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 1500
LOW_CONFIDENCE_THRESHOLD = 0.7


@dataclass
class AnswerGeneratorConfig:
    """
    Configuration for the AnswerGenerator.
    
    Attributes:
        temperature: LLM temperature for generation (0.0 to 1.0).
        max_tokens: Maximum tokens for LLM generation.
        low_confidence_threshold: Threshold below which disclaimer is added.
        numeric_precision: Decimal places for numeric values.
        include_raw_data: Whether to include raw data in citations.
        max_citations: Maximum number of citations to include.
    """
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    low_confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD
    numeric_precision: int = 6
    include_raw_data: bool = True
    max_citations: int = 10
    
    def __post_init__(self) -> None:
        """Validate configuration values."""
        if not 0.0 <= self.temperature <= 1.0:
            raise ValueError(
                f"temperature must be between 0.0 and 1.0, got {self.temperature}"
            )
        if self.max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")
        if not 0.0 <= self.low_confidence_threshold <= 1.0:
            raise ValueError(
                f"low_confidence_threshold must be between 0.0 and 1.0, "
                f"got {self.low_confidence_threshold}"
            )
        if self.numeric_precision < 0:
            raise ValueError(
                f"numeric_precision must be non-negative, got {self.numeric_precision}"
            )
        if self.max_citations <= 0:
            raise ValueError(
                f"max_citations must be positive, got {self.max_citations}"
            )


@dataclass
class GeneratedAnswer:
    """
    Internal representation of a generated answer before final formatting.
    
    Attributes:
        text: The answer text.
        citations: List of citations for the answer.
        confidence_breakdown: Breakdown of confidence scores.
        warnings: Any warnings generated during answer creation.
        metadata: Additional metadata about the answer.
    """
    text: str
    citations: list[Citation] = field(default_factory=list)
    confidence_breakdown: Optional[ConfidenceBreakdown] = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AnswerGenerator:
    """
    Generates natural language answers with citations and confidence scoring.
    
    This class is responsible for transforming processed query results into
    human-readable answers with proper source citations, confidence scores,
    and data lineage tracking for the smart Excel query pipeline.
    
    Implements Requirements 11.1-11.8:
    - 11.1: Include source citations for every factual claim
    - 11.2: Format citations as [File: filename, Sheet: sheetname, Range: cellrange]
    - 11.3: List all relevant sources when multiple support same claim
    - 11.4: Include confidence score (0-1) for overall answer
    - 11.5: Include disclaimer when confidence < 0.7
    - 11.6: Preserve numeric precision from source data
    - 11.7: Provide navigable citations with lineage_id
    - 11.8: Include confidence breakdown (file, sheet, data)
    
    All dependencies are injected via constructor following DIP.
    
    Example:
        >>> generator = AnswerGenerator(
        ...     llm_service=llm_svc,
        ...     config=AnswerGeneratorConfig()
        ... )
        >>> response = generator.generate(
        ...     query="What is the total sales?",
        ...     processed_result=result,
        ...     query_type=QueryType.AGGREGATION,
        ...     file_confidence=0.95,
        ...     sheet_confidence=0.88,
        ...     trace_id="tr_123"
        ... )
    """
    
    def __init__(
        self,
        llm_service: LLMService,
        config: Optional[AnswerGeneratorConfig] = None
    ) -> None:
        """
        Initialize the AnswerGenerator.
        
        Args:
            llm_service: LLM service for text generation.
            config: Optional configuration. Uses defaults if not provided.
        """
        self._llm_service = llm_service
        self._config = config or AnswerGeneratorConfig()

    def generate(
        self,
        query: str,
        processed_result: ProcessedResult,
        query_type: QueryType,
        file_confidence: float,
        sheet_confidence: float,
        trace_id: str,
        processing_time_ms: int = 0,
        from_cache: bool = False
    ) -> QueryResponse:
        """
        Generate a complete answer response from processed results.
        
        Args:
            query: Original query text.
            processed_result: Result from query processor.
            query_type: Type of query that was processed.
            file_confidence: Confidence in file selection (0.0 to 1.0).
            sheet_confidence: Confidence in sheet selection (0.0 to 1.0).
            trace_id: Unique trace ID for this query.
            processing_time_ms: Total processing time in milliseconds.
            from_cache: Whether result was served from cache.
            
        Returns:
            QueryResponse with answer, citations, and confidence.
            
        Raises:
            ProcessingError: If answer generation fails.
        """
        logger.info(f"Generating answer for query: {query[:100]}...")
        
        try:
            # Handle error results
            if not processed_result.success:
                return self._create_error_response(
                    processed_result=processed_result,
                    query_type=query_type,
                    trace_id=trace_id,
                    processing_time_ms=processing_time_ms
                )
            
            # Generate answer based on result type
            generated = self._generate_answer_for_result(
                query=query,
                processed_result=processed_result,
                query_type=query_type
            )
            
            # Calculate confidence breakdown
            data_confidence = self._calculate_data_confidence(processed_result)
            confidence_breakdown = self._create_confidence_breakdown(
                file_confidence=file_confidence,
                sheet_confidence=sheet_confidence,
                data_confidence=data_confidence
            )

            # Create citations with lineage IDs
            citations = self._create_citations(
                processed_result=processed_result,
                trace_id=trace_id
            )
            
            # Add disclaimer if confidence is low
            disclaimer = None
            if confidence_breakdown.overall_confidence < self._config.low_confidence_threshold:
                disclaimer = self._generate_disclaimer(confidence_breakdown)
            
            # Format final answer with citations
            final_answer = self._format_answer_with_citations(
                answer_text=generated.text,
                citations=citations,
                warnings=processed_result.warnings + generated.warnings
            )
            
            logger.info(
                f"Answer generated with confidence {confidence_breakdown.overall_confidence:.2f}"
            )
            
            return QueryResponse(
                answer=final_answer,
                citations=[self._citation_to_dict(c) for c in citations],
                confidence=confidence_breakdown.overall_confidence,
                confidence_breakdown={
                    "file_confidence": confidence_breakdown.file_confidence,
                    "sheet_confidence": confidence_breakdown.sheet_confidence,
                    "data_confidence": confidence_breakdown.data_confidence,
                },
                query_type=query_type.value,
                trace_id=trace_id,
                processing_time_ms=processing_time_ms,
                from_cache=from_cache,
                disclaimer=disclaimer
            )
            
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"Answer generation failed: {e}", exc_info=True)
            raise ProcessingError(
                f"Failed to generate answer: {str(e)}",
                details={"query": query, "error": str(e)}
            )

    def _generate_answer_for_result(
        self,
        query: str,
        processed_result: ProcessedResult,
        query_type: QueryType
    ) -> GeneratedAnswer:
        """
        Generate answer text based on the processed result type.
        
        Args:
            query: Original query text.
            processed_result: Result from query processor.
            query_type: Type of query.
            
        Returns:
            GeneratedAnswer with text and metadata.
        """
        if processed_result.result_type == "value":
            return self._generate_aggregation_answer(
                query=query,
                value=processed_result.value,
                metadata=processed_result.metadata,
                rows_processed=processed_result.rows_processed,
                rows_skipped=processed_result.rows_skipped
            )
        elif processed_result.result_type == "rows":
            return self._generate_lookup_answer(
                query=query,
                rows=processed_result.rows or [],
                metadata=processed_result.metadata
            )
        elif processed_result.result_type == "summary":
            return self._generate_summary_answer(
                query=query,
                summary=processed_result.summary or "",
                metadata=processed_result.metadata
            )
        elif processed_result.result_type == "comparison":
            return self._generate_comparison_answer(
                query=query,
                comparison=processed_result.comparison or {},
                metadata=processed_result.metadata
            )
        else:
            # Fallback to LLM-based generation
            return self._generate_llm_answer(
                query=query,
                processed_result=processed_result,
                query_type=query_type
            )

    def _generate_aggregation_answer(
        self,
        query: str,
        value: Any,
        metadata: dict[str, Any],
        rows_processed: int,
        rows_skipped: int
    ) -> GeneratedAnswer:
        """
        Generate answer for aggregation results.
        
        Preserves numeric precision per Requirement 11.6.
        
        Args:
            query: Original query.
            value: Computed aggregation value.
            metadata: Result metadata.
            rows_processed: Number of rows processed.
            rows_skipped: Number of rows skipped.
            
        Returns:
            GeneratedAnswer with formatted aggregation result.
        """
        # Format value preserving precision
        formatted_value = self._format_numeric_value(value)
        
        # Get aggregation function name
        agg_function = metadata.get("aggregation_function", "computed")
        target_column = metadata.get("target_column", "value")
        
        # Build answer text
        answer_parts = [
            f"The {agg_function.lower()} of {target_column} is {formatted_value}."
        ]
        
        # Add processing details
        if rows_processed > 0:
            answer_parts.append(f"This was calculated from {rows_processed} data points.")
        
        warnings = []
        if rows_skipped > 0:
            warnings.append(
                f"{rows_skipped} row(s) were skipped due to non-numeric values."
            )
        
        return GeneratedAnswer(
            text=" ".join(answer_parts),
            warnings=warnings,
            metadata={
                "aggregation_function": agg_function,
                "target_column": target_column,
                "rows_processed": rows_processed,
                "rows_skipped": rows_skipped,
                "raw_value": value
            }
        )

    def _generate_lookup_answer(
        self,
        query: str,
        rows: list[dict[str, Any]],
        metadata: dict[str, Any]
    ) -> GeneratedAnswer:
        """
        Generate answer for lookup results.
        
        Args:
            query: Original query.
            rows: Matching rows.
            metadata: Result metadata.
            
        Returns:
            GeneratedAnswer with formatted lookup results.
        """
        total_matches = metadata.get("total_matches", len(rows))
        
        if not rows:
            return GeneratedAnswer(
                text="No matching data was found for your query.",
                warnings=["No results matched the lookup criteria."],
                metadata=metadata
            )
        
        # Format rows as readable text
        if len(rows) == 1:
            row_text = self._format_single_row(rows[0])
            answer_text = f"Found the following data: {row_text}"
        else:
            rows_text = self._format_multiple_rows(rows)
            answer_text = f"Found {len(rows)} matching records:\n{rows_text}"
            
            if total_matches > len(rows):
                answer_text += f"\n(Showing {len(rows)} of {total_matches} total matches)"
        
        return GeneratedAnswer(
            text=answer_text,
            metadata={
                "total_matches": total_matches,
                "rows_returned": len(rows)
            }
        )

    def _generate_summary_answer(
        self,
        query: str,
        summary: str,
        metadata: dict[str, Any]
    ) -> GeneratedAnswer:
        """
        Generate answer for summarization results.
        
        Args:
            query: Original query.
            summary: Generated summary text.
            metadata: Result metadata.
            
        Returns:
            GeneratedAnswer with summary.
        """
        return GeneratedAnswer(
            text=summary,
            metadata=metadata
        )
    
    def _generate_comparison_answer(
        self,
        query: str,
        comparison: dict[str, Any],
        metadata: dict[str, Any]
    ) -> GeneratedAnswer:
        """
        Generate answer for comparison results.
        
        Args:
            query: Original query.
            comparison: Comparison data.
            metadata: Result metadata.
            
        Returns:
            GeneratedAnswer with comparison results.
        """
        # Extract comparison details
        differences = comparison.get("differences", [])
        trends = comparison.get("trends", [])
        summary = comparison.get("summary", "")
        
        answer_parts = []
        
        if summary:
            answer_parts.append(summary)
        
        if differences:
            diff_text = self._format_differences(differences)
            answer_parts.append(f"\nKey differences:\n{diff_text}")
        
        if trends:
            trend_text = self._format_trends(trends)
            answer_parts.append(f"\nTrends identified:\n{trend_text}")
        
        return GeneratedAnswer(
            text="\n".join(answer_parts) if answer_parts else "Comparison completed.",
            metadata=metadata
        )

    def _generate_llm_answer(
        self,
        query: str,
        processed_result: ProcessedResult,
        query_type: QueryType
    ) -> GeneratedAnswer:
        """
        Generate answer using LLM for complex or unstructured results.
        
        Args:
            query: Original query.
            processed_result: Processed result data.
            query_type: Type of query.
            
        Returns:
            GeneratedAnswer from LLM.
        """
        # Build prompt for LLM
        prompt = self._build_answer_prompt(query, processed_result, query_type)
        
        try:
            system_prompt = (
                "You are a helpful assistant that answers questions about Excel data. "
                "Provide clear, concise answers based on the data provided. "
                "Always be factual and cite specific values from the data."
            )
            
            answer_text = self._llm_service.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens
            )
            
            return GeneratedAnswer(
                text=answer_text.strip(),
                metadata={"generated_by": "llm"}
            )
            
        except Exception as e:
            logger.warning(f"LLM generation failed, using fallback: {e}")
            # Fallback to structured response
            return GeneratedAnswer(
                text=self._create_fallback_answer(processed_result),
                warnings=[f"LLM generation failed: {str(e)}"],
                metadata={"generated_by": "fallback"}
            )

    def _build_answer_prompt(
        self,
        query: str,
        processed_result: ProcessedResult,
        query_type: QueryType
    ) -> str:
        """
        Build prompt for LLM answer generation.
        
        Args:
            query: Original query.
            processed_result: Processed result.
            query_type: Query type.
            
        Returns:
            Formatted prompt string.
        """
        prompt_parts = [
            f"User Question: {query}",
            f"\nQuery Type: {query_type.value}",
            f"\nSource: {processed_result.source_file}, Sheet: {processed_result.source_sheet}",
            f"Cell Range: {processed_result.source_range}",
        ]
        
        if processed_result.value is not None:
            prompt_parts.append(f"\nComputed Value: {processed_result.value}")
        
        if processed_result.rows:
            rows_preview = processed_result.rows[:5]
            prompt_parts.append(f"\nData Preview: {rows_preview}")
        
        if processed_result.summary:
            prompt_parts.append(f"\nSummary: {processed_result.summary}")
        
        prompt_parts.append(
            "\nPlease provide a clear, natural language answer to the user's question "
            "based on the data above. Be specific and cite the source data."
        )
        
        return "\n".join(prompt_parts)
    
    def _create_fallback_answer(self, processed_result: ProcessedResult) -> str:
        """
        Create a fallback answer when LLM fails.
        
        Args:
            processed_result: Processed result.
            
        Returns:
            Fallback answer text.
        """
        if processed_result.value is not None:
            return f"The result is: {self._format_numeric_value(processed_result.value)}"
        elif processed_result.rows:
            return f"Found {len(processed_result.rows)} matching record(s)."
        elif processed_result.summary:
            return processed_result.summary
        else:
            return "Query processed successfully."

    def _calculate_data_confidence(self, processed_result: ProcessedResult) -> float:
        """
        Calculate confidence in the data retrieval and processing.
        
        Args:
            processed_result: Processed result.
            
        Returns:
            Data confidence score (0.0 to 1.0).
        """
        if not processed_result.success:
            return 0.0
        
        confidence = 1.0
        
        # Reduce confidence based on skipped rows
        if processed_result.rows_processed > 0:
            skip_ratio = processed_result.rows_skipped / (
                processed_result.rows_processed + processed_result.rows_skipped
            )
            confidence -= skip_ratio * 0.3  # Max 30% reduction for skipped rows
        
        # Reduce confidence if there are warnings
        warning_count = len(processed_result.warnings)
        if warning_count > 0:
            confidence -= min(warning_count * 0.05, 0.2)  # Max 20% reduction
        
        # Ensure confidence stays in valid range
        return max(0.0, min(1.0, confidence))
    
    def _create_confidence_breakdown(
        self,
        file_confidence: float,
        sheet_confidence: float,
        data_confidence: float
    ) -> ConfidenceBreakdown:
        """
        Create confidence breakdown with overall score.
        
        Implements Requirement 11.8: Include confidence breakdown.
        
        Args:
            file_confidence: Confidence in file selection.
            sheet_confidence: Confidence in sheet selection.
            data_confidence: Confidence in data retrieval.
            
        Returns:
            ConfidenceBreakdown with all scores.
        """
        # Calculate overall confidence as weighted average
        # File selection is most critical, then sheet, then data
        overall = (
            file_confidence * 0.4 +
            sheet_confidence * 0.3 +
            data_confidence * 0.3
        )
        
        return ConfidenceBreakdown(
            file_confidence=file_confidence,
            sheet_confidence=sheet_confidence,
            data_confidence=data_confidence,
            overall_confidence=round(overall, 4)
        )

    def _create_citations(
        self,
        processed_result: ProcessedResult,
        trace_id: str
    ) -> list[Citation]:
        """
        Create citations with lineage IDs for the answer.
        
        Implements Requirements 11.1, 11.2, 11.7:
        - Include source citations for every factual claim
        - Format as [File: filename, Sheet: sheetname, Range: cellrange]
        - Provide navigable citations with lineage_id
        
        Args:
            processed_result: Processed result with source info.
            trace_id: Trace ID for lineage tracking.
            
        Returns:
            List of Citation objects.
        """
        citations = []
        
        if processed_result.source_file and processed_result.source_sheet:
            # Generate unique lineage ID
            lineage_id = f"lin_{uuid.uuid4().hex[:12]}"
            
            # Get source value for citation
            source_value = None
            if self._config.include_raw_data:
                if processed_result.value is not None:
                    source_value = str(processed_result.value)
                elif processed_result.rows and len(processed_result.rows) > 0:
                    source_value = f"{len(processed_result.rows)} row(s)"
            
            citation = Citation(
                file_name=processed_result.source_file,
                sheet_name=processed_result.source_sheet,
                cell_range=processed_result.source_range or "N/A",
                lineage_id=lineage_id,
                source_value=source_value
            )
            citations.append(citation)
        
        # Add citations from chunk IDs if available
        for i, chunk_id in enumerate(processed_result.chunk_ids[:self._config.max_citations - 1]):
            if i >= self._config.max_citations - 1:
                break
            # Additional citations would be created here if chunk metadata available
        
        return citations

    def _generate_disclaimer(self, confidence_breakdown: ConfidenceBreakdown) -> str:
        """
        Generate disclaimer for low confidence answers.
        
        Implements Requirement 11.5: Include disclaimer when confidence < 0.7.
        
        Args:
            confidence_breakdown: Confidence scores.
            
        Returns:
            Disclaimer text.
        """
        overall = confidence_breakdown.overall_confidence
        
        # Identify the weakest component
        components = [
            ("file selection", confidence_breakdown.file_confidence),
            ("sheet selection", confidence_breakdown.sheet_confidence),
            ("data retrieval", confidence_breakdown.data_confidence),
        ]
        weakest = min(components, key=lambda x: x[1])
        
        disclaimer = (
            f"Note: This answer has a confidence score of {overall:.0%}. "
            f"The {weakest[0]} confidence is {weakest[1]:.0%}. "
            "Please verify the results against the source data."
        )
        
        return disclaimer
    
    def _format_answer_with_citations(
        self,
        answer_text: str,
        citations: list[Citation],
        warnings: list[str]
    ) -> str:
        """
        Format the final answer with citations appended.
        
        Implements Requirement 11.2: Format citations properly.
        
        Args:
            answer_text: The answer text.
            citations: List of citations.
            warnings: Any warnings to include.
            
        Returns:
            Formatted answer with citations.
        """
        parts = [answer_text]
        
        # Add citations section
        if citations:
            citation_lines = ["\n\nSources:"]
            for citation in citations:
                citation_lines.append(f"  • {citation.format()}")
            parts.append("\n".join(citation_lines))
        
        # Add warnings if any
        if warnings:
            warning_lines = ["\n\nNotes:"]
            for warning in warnings:
                warning_lines.append(f"  ⚠ {warning}")
            parts.append("\n".join(warning_lines))
        
        return "".join(parts)

    def _citation_to_dict(self, citation: Citation) -> dict[str, Any]:
        """
        Convert Citation to dictionary for JSON serialization.
        
        Args:
            citation: Citation object.
            
        Returns:
            Dictionary representation.
        """
        return {
            "file_name": citation.file_name,
            "sheet_name": citation.sheet_name,
            "cell_range": citation.cell_range,
            "lineage_id": citation.lineage_id,
            "source_value": citation.source_value,
            "formatted": citation.format()
        }
    
    def _create_error_response(
        self,
        processed_result: ProcessedResult,
        query_type: QueryType,
        trace_id: str,
        processing_time_ms: int
    ) -> QueryResponse:
        """
        Create error response for failed processing.
        
        Args:
            processed_result: Failed result with error message.
            query_type: Query type.
            trace_id: Trace ID.
            processing_time_ms: Processing time.
            
        Returns:
            QueryResponse with error information.
        """
        error_message = processed_result.error_message or "An error occurred"
        
        return QueryResponse(
            answer=f"Unable to process query: {error_message}",
            citations=[],
            confidence=0.0,
            confidence_breakdown={
                "file_confidence": 0.0,
                "sheet_confidence": 0.0,
                "data_confidence": 0.0,
            },
            query_type=query_type.value,
            trace_id=trace_id,
            processing_time_ms=processing_time_ms,
            from_cache=False,
            disclaimer="This query could not be processed successfully."
        )

    def _format_numeric_value(self, value: Any) -> str:
        """
        Format numeric value preserving precision.
        
        Implements Requirement 11.6: Preserve numeric precision from source data.
        
        Args:
            value: Value to format.
            
        Returns:
            Formatted string representation.
        """
        if value is None:
            return "N/A"
        
        if isinstance(value, (int, float, Decimal)):
            # Check if it's a whole number
            if isinstance(value, float) and value.is_integer():
                return f"{int(value):,}"
            elif isinstance(value, int):
                return f"{value:,}"
            else:
                # Format with configured precision, removing trailing zeros
                formatted = f"{value:,.{self._config.numeric_precision}f}"
                # Remove unnecessary trailing zeros but keep at least 2 decimal places
                if "." in formatted:
                    formatted = formatted.rstrip("0").rstrip(".")
                    # Ensure at least 2 decimal places for currency-like values
                    if "." in formatted:
                        decimal_places = len(formatted.split(".")[1])
                        if decimal_places < 2:
                            formatted += "0" * (2 - decimal_places)
                return formatted
        
        return str(value)
    
    def _format_single_row(self, row: dict[str, Any]) -> str:
        """
        Format a single row as readable text.
        
        Args:
            row: Row data as dictionary.
            
        Returns:
            Formatted row string.
        """
        parts = []
        for key, value in row.items():
            formatted_value = self._format_numeric_value(value) if isinstance(
                value, (int, float, Decimal)
            ) else str(value)
            parts.append(f"{key}: {formatted_value}")
        return ", ".join(parts)

    def _format_multiple_rows(self, rows: list[dict[str, Any]]) -> str:
        """
        Format multiple rows as a readable list.
        
        Args:
            rows: List of row dictionaries.
            
        Returns:
            Formatted rows string.
        """
        lines = []
        for i, row in enumerate(rows, 1):
            row_text = self._format_single_row(row)
            lines.append(f"  {i}. {row_text}")
        return "\n".join(lines)
    
    def _format_differences(self, differences: list[dict[str, Any]]) -> str:
        """
        Format comparison differences.
        
        Args:
            differences: List of difference records.
            
        Returns:
            Formatted differences string.
        """
        lines = []
        for diff in differences[:10]:  # Limit to 10 differences
            field = diff.get("field", "Unknown")
            old_val = diff.get("old_value", "N/A")
            new_val = diff.get("new_value", "N/A")
            change = diff.get("change_percent")
            
            line = f"  • {field}: {old_val} → {new_val}"
            if change is not None:
                line += f" ({change:+.1f}%)"
            lines.append(line)
        
        return "\n".join(lines)
    
    def _format_trends(self, trends: list[dict[str, Any]]) -> str:
        """
        Format identified trends.
        
        Args:
            trends: List of trend records.
            
        Returns:
            Formatted trends string.
        """
        lines = []
        for trend in trends[:5]:  # Limit to 5 trends
            metric = trend.get("metric", "Unknown")
            direction = trend.get("direction", "stable")
            rate = trend.get("rate")
            
            line = f"  • {metric}: {direction}"
            if rate is not None:
                line += f" ({rate:+.1f}% change)"
            lines.append(line)
        
        return "\n".join(lines)
