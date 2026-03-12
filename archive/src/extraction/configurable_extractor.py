"""
Configurable extraction with multiple backend strategies.

This module provides a unified interface for Excel extraction that can use
different backends (openpyxl, Gemini, LlamaParse) based on configuration.
"""

import logging
from datetime import datetime
from typing import Optional

from src.extraction.content_extractor import ContentExtractor, CorruptedFileError
from src.extraction.extraction_strategy import (
    ExtractionConfig,
    ExtractionQuality,
    ExtractionStrategy,
)
from src.extraction.sheet_summarizer import SheetSummarizer
from src.models.domain_models import SheetData, WorkbookData


logger = logging.getLogger(__name__)


class ConfigurableExtractor:
    """
    Configurable Excel extractor with multiple backend strategies.
    
    Supports:
    - openpyxl (default, fast, local)
    - Google Gemini (multimodal, fallback)
    - LlamaParse (document understanding)
    - Auto strategy selection
    """
    
    def __init__(self, config: Optional[ExtractionConfig] = None):
        """
        Initialize the configurable extractor.
        
        Args:
            config: Extraction configuration (uses defaults if not provided)
        """
        self.config = config or ExtractionConfig()
        self.logger = logging.getLogger(__name__)
        
        # Initialize extractors
        self.openpyxl_extractor = ContentExtractor(
            max_rows_per_sheet=self.config.max_rows_per_sheet
        )
        
        # Initialize optional extractors
        self.gemini_extractor = None
        if self.config.enable_gemini:
            try:
                from src.extraction.gemini_extractor import GeminiExcelExtractor
                self.gemini_extractor = GeminiExcelExtractor(self.config)
                self.logger.info("Gemini extractor initialized")
            except ImportError:
                self.logger.warning("Gemini extractor not available")
        
        self.llama_extractor = None
        if self.config.enable_llamaparse:
            try:
                from src.extraction.llama_extractor import LlamaParseExtractor
                self.llama_extractor = LlamaParseExtractor(self.config)
                self.logger.info("LlamaParse extractor initialized")
            except ImportError:
                self.logger.warning("LlamaParse extractor not available")
        
        # Initialize summarizer
        self.summarizer = None
        if self.config.enable_llm_summarization:
            self.summarizer = SheetSummarizer(self.config)
    
    def extract_workbook_sync(
        self,
        file_content: bytes,
        file_name: str,
        file_id: str = "",
        file_path: str = "",
        modified_time: Optional[datetime] = None
    ) -> WorkbookData:
        """
        Synchronous extraction without LLM summarization.
        
        This method is used when LLM summarization is disabled or when
        async operations are not supported. It uses only openpyxl extraction.
        
        Args:
            file_content: Raw bytes of Excel file
            file_name: File name
            file_id: Google Drive file ID (optional)
            file_path: Full path in Google Drive (optional)
            modified_time: Last modified timestamp (optional)
            
        Returns:
            WorkbookData with extracted information
            
        Raises:
            CorruptedFileError: If file cannot be extracted
        """
        if modified_time is None:
            modified_time = datetime.now()
        
        # Use openpyxl extractor for synchronous extraction
        workbook_data = self.openpyxl_extractor.extract_workbook(
            file_content, file_id, file_name, file_path, modified_time
        )
        
        return workbook_data
    
    async def extract_workbook(
        self,
        file_content: bytes,
        file_id: str,
        file_name: str,
        file_path: str,
        modified_time: datetime,
        strategy: Optional[ExtractionStrategy] = None
    ) -> WorkbookData:
        """
        Extract workbook using specified or configured strategy.
        
        Args:
            file_content: Raw bytes of Excel file
            file_id: Google Drive file ID
            file_name: File name
            file_path: Full path in Google Drive
            modified_time: Last modified timestamp
            strategy: Optional strategy override (uses config default if not provided)
            
        Returns:
            WorkbookData with extracted information
            
        Raises:
            CorruptedFileError: If file cannot be extracted
        """
        # Determine strategy
        if strategy is None:
            strategy = self.config.default_strategy
        
        if strategy == ExtractionStrategy.AUTO or self.config.use_auto_strategy:
            return await self._smart_extract(
                file_content, file_id, file_name, file_path, modified_time
            )
        
        # Extract using specified strategy
        workbook_data = await self._extract_with_strategy(
            strategy, file_content, file_id, file_name, file_path, modified_time
        )
        
        # Generate LLM summaries if enabled
        if self.config.enable_llm_summarization and self.summarizer:
            await self._add_llm_summaries(workbook_data, file_name)
        
        return workbook_data
    
    async def _extract_with_strategy(
        self,
        strategy: ExtractionStrategy,
        file_content: bytes,
        file_id: str,
        file_name: str,
        file_path: str,
        modified_time: datetime
    ) -> WorkbookData:
        """Extract using a specific strategy."""
        
        if strategy == ExtractionStrategy.OPENPYXL:
            return self.openpyxl_extractor.extract_workbook(
                file_content, file_id, file_name, file_path, modified_time
            )
        
        elif strategy == ExtractionStrategy.GEMINI:
            if not self.gemini_extractor:
                raise ValueError("Gemini extractor not enabled or available")
            return await self.gemini_extractor.extract_workbook(
                file_content, file_id, file_name, file_path, modified_time
            )
        
        elif strategy == ExtractionStrategy.LLAMAPARSE:
            if not self.llama_extractor:
                raise ValueError("LlamaParse extractor not enabled or available")
            return await self.llama_extractor.extract_workbook(
                file_content, file_id, file_name, file_path, modified_time
            )
        
        else:
            raise ValueError(f"Unknown extraction strategy: {strategy}")
    
    async def _smart_extract(
        self,
        file_content: bytes,
        file_id: str,
        file_name: str,
        file_path: str,
        modified_time: datetime
    ) -> WorkbookData:
        """
        Automatically choose the best extraction strategy.
        
        Strategy:
        1. Try openpyxl first (fast and free)
        2. Evaluate extraction quality
        3. Fall back to Gemini if quality is low and Gemini is enabled
        """
        self.logger.info(f"Smart extraction for {file_name}")
        
        # Try openpyxl first
        try:
            workbook_data = self.openpyxl_extractor.extract_workbook(
                file_content, file_id, file_name, file_path, modified_time
            )
            
            # Evaluate extraction quality
            quality = self._evaluate_extraction_quality(workbook_data)
            
            self.logger.info(
                f"openpyxl extraction quality for {file_name}: {quality.score:.2f}"
            )
            
            # If quality is good, use openpyxl result
            if quality.is_high_quality:
                self.logger.info(f"Using openpyxl extraction for {file_name}")
                return workbook_data
            
            # If quality is low and Gemini is available, try Gemini
            if (
                quality.score < self.config.complexity_threshold
                and self.gemini_extractor
                and self.config.gemini_fallback_on_error
            ):
                self.logger.info(
                    f"Low quality extraction ({quality.score:.2f}), "
                    f"falling back to Gemini for {file_name}"
                )
                return await self.gemini_extractor.extract_workbook(
                    file_content, file_id, file_name, file_path, modified_time
                )
            
            # Return openpyxl result even if quality is low
            return workbook_data
            
        except CorruptedFileError as e:
            # Try Gemini as last resort
            if self.gemini_extractor and self.config.gemini_fallback_on_error:
                self.logger.info(
                    f"openpyxl failed for {file_name}, trying Gemini: {e}"
                )
                return await self.gemini_extractor.extract_workbook(
                    file_content, file_id, file_name, file_path, modified_time
                )
            raise
    
    def _evaluate_extraction_quality(self, workbook_data: WorkbookData) -> ExtractionQuality:
        """
        Evaluate the quality of extraction results.
        
        Args:
            workbook_data: Extracted workbook data
            
        Returns:
            ExtractionQuality metrics
        """
        if not workbook_data.sheets:
            return ExtractionQuality(
                score=0.0,
                has_headers=False,
                has_data=False,
                data_completeness=0.0,
                structure_clarity=0.0,
                extraction_errors=1
            )
        
        # Analyze sheets
        total_sheets = len(workbook_data.sheets)
        sheets_with_headers = sum(1 for s in workbook_data.sheets if s.headers)
        sheets_with_data = sum(1 for s in workbook_data.sheets if s.rows)
        
        # Calculate data completeness
        total_cells = 0
        non_empty_cells = 0
        
        for sheet in workbook_data.sheets:
            for row in sheet.rows[:100]:  # Sample first 100 rows
                for value in row.values():
                    total_cells += 1
                    if value is not None and value != "":
                        non_empty_cells += 1
        
        data_completeness = non_empty_cells / total_cells if total_cells > 0 else 0.0
        
        # Calculate structure clarity
        avg_columns = sum(s.column_count for s in workbook_data.sheets) / total_sheets
        structure_clarity = min(avg_columns / 20.0, 1.0)  # Normalize to 0-1
        
        # Calculate overall score
        has_headers = sheets_with_headers > 0
        has_data = sheets_with_data > 0
        
        score = (
            (0.3 if has_headers else 0.0) +
            (0.3 if has_data else 0.0) +
            (0.2 * data_completeness) +
            (0.2 * structure_clarity)
        )
        
        return ExtractionQuality(
            score=score,
            has_headers=has_headers,
            has_data=has_data,
            data_completeness=data_completeness,
            structure_clarity=structure_clarity,
            extraction_errors=0
        )
    
    async def _add_llm_summaries(
        self,
        workbook_data: WorkbookData,
        file_name: str
    ) -> None:
        """
        Add LLM-generated summaries to sheets.
        
        Args:
            workbook_data: Workbook data to enhance
            file_name: File name for context
        """
        if not self.summarizer:
            return
        
        self.logger.info(f"Generating LLM summaries for {len(workbook_data.sheets)} sheets")
        
        for sheet in workbook_data.sheets:
            try:
                summary = await self.summarizer.generate_sheet_summary(
                    sheet, file_name
                )
                if summary:
                    sheet.llm_summary = summary
                    sheet.summary_generated_at = datetime.now()
                    self.logger.debug(
                        f"Generated summary for sheet '{sheet.sheet_name}': {summary[:100]}..."
                    )
            except Exception as e:
                self.logger.error(
                    f"Failed to generate summary for sheet '{sheet.sheet_name}': {e}"
                )
    
    def get_failed_files(self):
        """Get list of files that failed extraction."""
        return self.openpyxl_extractor.get_failed_files()
    
    def clear_failed_files(self):
        """Clear the failed files list."""
        self.openpyxl_extractor.clear_failed_files()
