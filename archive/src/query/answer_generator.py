"""
Main answer generator for query results.

This module orchestrates the answer generation process, integrating prompt building,
data formatting, citation generation, and confidence scoring to produce complete
query results.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from src.abstractions.llm_service import LLMService
from src.models.domain_models import (
    QueryResult,
    RetrievedData,
    RankedFile,
    SheetSelection,
    ComparisonResult
)
from src.query.prompt_builder import PromptBuilder, AnswerType, Language
from src.query.data_formatter import DataFormatter
from src.query.citation_generator import CitationGenerator
from src.query.confidence_scorer import ConfidenceScorer

logger = logging.getLogger(__name__)


class AnswerGenerator:
    """
    Generates natural language answers from retrieved data.
    
    Orchestrates the complete answer generation pipeline including data formatting,
    prompt building, LLM generation, citation addition, and confidence scoring.
    """
    
    def __init__(
        self,
        llm_service: LLMService,
        language: str = "en",
        temperature: float = 0.3,
        max_tokens: int = 1000
    ):
        """
        Initialize the answer generator.
        
        Args:
            llm_service: LLM service for text generation
            language: Language code ('en' or 'th')
            temperature: LLM temperature for generation
            max_tokens: Maximum tokens for LLM generation
        """
        self.llm_service = llm_service
        self.language = language
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize components
        self.prompt_builder = PromptBuilder()
        self.data_formatter = DataFormatter(language=language)
        self.citation_generator = CitationGenerator(language=language)
        self.confidence_scorer = ConfidenceScorer(language=language)
    
    def generate_answer(
        self,
        query: str,
        retrieved_data: List[RetrievedData],
        ranked_files: Optional[List[RankedFile]] = None,
        sheet_selection: Optional[SheetSelection] = None,
        answer_type: Optional[AnswerType] = None,
        additional_context: Optional[str] = None,
        expected_data_points: Optional[int] = None,
        query_entities: Optional[List[str]] = None
    ) -> QueryResult:
        """
        Generate a complete answer for a query.
        
        Args:
            query: The user's question
            retrieved_data: Data retrieved from Excel files
            ranked_files: Ranked file candidates
            sheet_selection: Sheet selection result
            answer_type: Type of answer to generate (auto-detected if None)
            additional_context: Optional additional context
            expected_data_points: Expected number of data points
            query_entities: Entities extracted from query
            
        Returns:
            QueryResult with answer, sources, and confidence
        """
        start_time = time.time()
        
        try:
            # Clear previous citations
            self.citation_generator.clear()
            
            # Detect language if needed
            detected_language = self.prompt_builder.detect_language(query)
            if detected_language == Language.THAI:
                self.language = "th"
                self.data_formatter.language = "th"
                self.citation_generator.language = "th"
                self.confidence_scorer.language = "th"
            
            # Infer answer type if not provided
            if answer_type is None:
                answer_type = self.prompt_builder.infer_answer_type(query, retrieved_data)
            
            # Format the data
            formatted_data = self._format_data_for_answer(retrieved_data, answer_type)
            
            # Build the prompt
            prompt = self.prompt_builder.build_answer_prompt(
                query=query,
                retrieved_data=retrieved_data,
                answer_type=answer_type,
                language=detected_language,
                additional_context=additional_context
            )
            
            # Generate answer using LLM
            raw_answer = self._generate_with_llm(prompt)
            
            # Add citations
            annotated_answer, citation_list = self.citation_generator.annotate_answer(
                answer=raw_answer,
                data_sources=retrieved_data,
                auto_annotate=True
            )
            
            # Combine answer with citations
            final_answer = f"{annotated_answer}\n{citation_list}"
            
            # Calculate confidence
            confidence_breakdown = self.confidence_scorer.calculate_confidence(
                query=query,
                retrieved_data=retrieved_data,
                ranked_files=ranked_files,
                sheet_selection=sheet_selection,
                expected_data_points=expected_data_points,
                query_entities=query_entities
            )
            
            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Create query result
            return QueryResult(
                answer=final_answer,
                confidence=confidence_breakdown.overall_confidence,
                sources=retrieved_data,
                clarification_needed=False,
                clarifying_questions=[],
                processing_time_ms=processing_time_ms,
                is_comparison=False,
                comparison_summary=None
            )
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}", exc_info=True)
            return self._create_error_result(query, str(e), time.time() - start_time)
    
    def generate_comparison_answer(
        self,
        query: str,
        comparison_result: ComparisonResult,
        ranked_files: Optional[List[RankedFile]] = None
    ) -> QueryResult:
        """
        Generate an answer for a comparison query.
        
        Args:
            query: The user's comparison question
            comparison_result: Result from comparison engine
            ranked_files: Ranked file candidates
            
        Returns:
            QueryResult with comparison answer
        """
        start_time = time.time()
        
        try:
            # Clear previous citations
            self.citation_generator.clear()
            
            # Detect language
            detected_language = self.prompt_builder.detect_language(query)
            if detected_language == Language.THAI:
                self.language = "th"
                self.data_formatter.language = "th"
                self.citation_generator.language = "th"
                self.confidence_scorer.language = "th"
            
            # Build comparison prompt
            prompt = self.prompt_builder.build_comparison_prompt(
                query=query,
                comparison_data={
                    "aligned_data": comparison_result.aligned_data,
                    "differences": comparison_result.differences,
                    "summary": comparison_result.summary
                },
                files_compared=comparison_result.files_compared,
                language=detected_language
            )
            
            # Generate answer using LLM
            raw_answer = self._generate_with_llm(prompt)
            
            # Add comparison sources
            sheets_used = {}  # Would be populated from comparison_result
            sources_text = self.citation_generator.format_comparison_sources(
                files_compared=comparison_result.files_compared,
                sheets_used=sheets_used
            )
            
            # Combine answer with sources
            final_answer = f"{raw_answer}\n{sources_text}"
            
            # Calculate confidence (comparison queries typically have moderate confidence)
            confidence = 0.75  # Base confidence for comparisons
            
            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Create query result
            return QueryResult(
                answer=final_answer,
                confidence=confidence,
                sources=[],  # Comparison doesn't use RetrievedData format
                clarification_needed=False,
                clarifying_questions=[],
                processing_time_ms=processing_time_ms,
                is_comparison=True,
                comparison_summary=comparison_result.differences
            )
            
        except Exception as e:
            logger.error(f"Error generating comparison answer: {e}", exc_info=True)
            return self._create_error_result(query, str(e), time.time() - start_time)
    
    def generate_formula_explanation(
        self,
        formula: str,
        cell_range: str,
        sheet_name: str,
        file_name: str,
        calculated_value: Optional[Any] = None
    ) -> str:
        """
        Generate an explanation for an Excel formula.
        
        Args:
            formula: The Excel formula
            cell_range: Cell range containing the formula
            sheet_name: Sheet name
            file_name: File name
            calculated_value: Optional calculated result
            
        Returns:
            Formula explanation string
        """
        try:
            # Detect language
            detected_language = Language.ENGLISH if self.language == "en" else Language.THAI
            
            # Build formula explanation prompt
            prompt = self.prompt_builder.build_formula_explanation_prompt(
                formula=formula,
                cell_range=cell_range,
                sheet_name=sheet_name,
                file_name=file_name,
                language=detected_language
            )
            
            # Generate explanation using LLM
            explanation = self._generate_with_llm(prompt, temperature=0.3)
            
            # Format with data formatter
            formatted = self.data_formatter.format_formula(
                formula=formula,
                calculated_value=calculated_value,
                include_explanation=False  # LLM provides the explanation
            )
            
            return f"{formatted}\n\n{explanation}"
            
        except Exception as e:
            logger.error(f"Error generating formula explanation: {e}", exc_info=True)
            # Fallback to basic formatting
            return self.data_formatter.format_formula(
                formula=formula,
                calculated_value=calculated_value,
                include_explanation=True
            )
    
    def _format_data_for_answer(
        self,
        retrieved_data: List[RetrievedData],
        answer_type: AnswerType
    ) -> str:
        """Format retrieved data based on answer type."""
        if not retrieved_data:
            return "No data available"
        
        # For table answers, format as table
        if answer_type == AnswerType.TABLE:
            first_data = retrieved_data[0].data
            if isinstance(first_data, list):
                column_formats = {}
                if retrieved_data[0].original_format:
                    # Use format for all columns (simplified)
                    pass
                return self.data_formatter.format_table(
                    rows=first_data,
                    column_formats=column_formats
                )
        
        # For list answers, format as list
        if answer_type == AnswerType.LIST:
            items = []
            for data in retrieved_data:
                if isinstance(data.data, list):
                    items.extend(data.data)
                else:
                    items.append(data.data)
            return self.data_formatter.format_list(items)
        
        # For other types, return formatted values
        formatted_values = []
        for data in retrieved_data:
            if data.original_format:
                formatted = self.data_formatter.format_number(
                    value=data.data,
                    excel_format=data.original_format
                )
            else:
                formatted = str(data.data)
            formatted_values.append(formatted)
        
        return ", ".join(formatted_values)
    
    def _generate_with_llm(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate text using LLM with error handling.
        
        Args:
            prompt: The prompt to send to LLM
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            
        Returns:
            Generated text
        """
        try:
            response = self.llm_service.generate(
                prompt=prompt,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens
            )
            return response.strip()
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}", exc_info=True)
            # Fallback to structured data presentation
            if self.language == "th":
                return "ขออภัย ไม่สามารถสร้างคำตอบได้ กรุณาดูข้อมูลที่ดึงมาด้านล่าง"
            else:
                return "Sorry, unable to generate answer. Please see the retrieved data below."
    
    def _create_error_result(
        self,
        query: str,
        error_message: str,
        elapsed_time: float
    ) -> QueryResult:
        """Create an error query result."""
        processing_time_ms = int(elapsed_time * 1000)
        
        if self.language == "th":
            answer = f"เกิดข้อผิดพลาดในการสร้างคำตอบ: {error_message}"
        else:
            answer = f"An error occurred while generating the answer: {error_message}"
        
        return QueryResult(
            answer=answer,
            confidence=0.0,
            sources=[],
            clarification_needed=False,
            clarifying_questions=[],
            processing_time_ms=processing_time_ms,
            is_comparison=False,
            comparison_summary=None
        )
    
    def generate_table_answer(
        self,
        query: str,
        table_data: List[Dict[str, Any]],
        file_name: str,
        sheet_name: str,
        cell_range: str,
        column_formats: Optional[Dict[str, str]] = None
    ) -> QueryResult:
        """
        Generate an answer for table data.
        
        Args:
            query: The user's question
            table_data: Table data as list of row dictionaries
            file_name: Source file name
            sheet_name: Source sheet name
            cell_range: Source cell range
            column_formats: Optional Excel formats for columns
            
        Returns:
            QueryResult with formatted table
        """
        start_time = time.time()
        
        try:
            # Format table
            formatted_table = self.data_formatter.format_table(
                rows=table_data,
                column_formats=column_formats
            )
            
            # Add citation
            citation = self.citation_generator.add_citation(
                file_name=file_name,
                sheet_name=sheet_name,
                cell_range=cell_range
            )
            
            # Create answer with table and citation
            if self.language == "th":
                answer = f"ตารางข้อมูลที่ตรงกับคำถาม:\n\n{formatted_table}\n\n{citation.format_full('th')}"
            else:
                answer = f"Table data matching your query:\n\n{formatted_table}\n\n{citation.format_full('en')}"
            
            # Create retrieved data object
            retrieved_data = [RetrievedData(
                file_name=file_name,
                file_path="",
                sheet_name=sheet_name,
                cell_range=cell_range,
                data=table_data,
                data_type="table",
                original_format=None
            )]
            
            # Calculate confidence
            confidence = 0.85  # High confidence for direct table retrieval
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            return QueryResult(
                answer=answer,
                confidence=confidence,
                sources=retrieved_data,
                clarification_needed=False,
                clarifying_questions=[],
                processing_time_ms=processing_time_ms,
                is_comparison=False,
                comparison_summary=None
            )
            
        except Exception as e:
            logger.error(f"Error generating table answer: {e}", exc_info=True)
            return self._create_error_result(query, str(e), time.time() - start_time)
    
    def generate_single_value_answer(
        self,
        query: str,
        value: Any,
        file_name: str,
        sheet_name: str,
        cell_range: str,
        excel_format: Optional[str] = None,
        data_type: str = "number"
    ) -> QueryResult:
        """
        Generate an answer for a single value.
        
        Args:
            query: The user's question
            value: The value to present
            file_name: Source file name
            sheet_name: Source sheet name
            cell_range: Source cell range
            excel_format: Optional Excel format
            data_type: Data type
            
        Returns:
            QueryResult with formatted value
        """
        start_time = time.time()
        
        try:
            # Format value
            if excel_format:
                formatted_value = self.data_formatter.format_number(
                    value=value,
                    excel_format=excel_format
                )
            else:
                formatted_value = str(value)
            
            # Add citation
            citation = self.citation_generator.add_citation(
                file_name=file_name,
                sheet_name=sheet_name,
                cell_range=cell_range
            )
            
            # Create answer
            if self.language == "th":
                answer = f"คำตอบ: {formatted_value} {citation.format_inline()}\n\n{citation.format_full('th')}"
            else:
                answer = f"Answer: {formatted_value} {citation.format_inline()}\n\n{citation.format_full('en')}"
            
            # Create retrieved data object
            retrieved_data = [RetrievedData(
                file_name=file_name,
                file_path="",
                sheet_name=sheet_name,
                cell_range=cell_range,
                data=value,
                data_type=data_type,
                original_format=excel_format
            )]
            
            # High confidence for single value retrieval
            confidence = 0.90
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            return QueryResult(
                answer=answer,
                confidence=confidence,
                sources=retrieved_data,
                clarification_needed=False,
                clarifying_questions=[],
                processing_time_ms=processing_time_ms,
                is_comparison=False,
                comparison_summary=None
            )
            
        except Exception as e:
            logger.error(f"Error generating single value answer: {e}", exc_info=True)
            return self._create_error_result(query, str(e), time.time() - start_time)
