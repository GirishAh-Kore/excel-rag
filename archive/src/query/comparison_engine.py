"""
Comparison Engine for comparing data across multiple Excel files.

This module provides the ComparisonEngine class that orchestrates the comparison
of data across multiple files, handling alignment, difference calculation, and
result formatting.
"""

import logging
from typing import List, Dict, Any, Optional

from src.models.domain_models import (
    ComparisonResult,
    AlignedData,
    SheetData,
    QueryResult
)
from src.query.sheet_aligner import SheetAligner
from src.query.difference_calculator import DifferenceCalculator
from src.query.comparison_formatter import ComparisonFormatter
from src.extraction.content_extractor import ContentExtractor
from src.gdrive.connector import GoogleDriveConnector
from src.abstractions.cache_service import CacheService

logger = logging.getLogger(__name__)


class ComparisonEngine:
    """
    Orchestrates comparison of data across multiple Excel files.
    
    This class coordinates the workflow of aligning sheets, calculating differences,
    and formatting results for comparison queries.
    """
    
    def __init__(
        self,
        gdrive_connector: GoogleDriveConnector,
        content_extractor: ContentExtractor,
        cache_service: Optional[CacheService] = None
    ):
        """
        Initialize the ComparisonEngine.
        
        Args:
            gdrive_connector: Google Drive connector for file access
            content_extractor: Content extractor for parsing Excel files
            cache_service: Optional cache service for caching aligned data
        """
        self.gdrive_connector = gdrive_connector
        self.content_extractor = content_extractor
        self.cache_service = cache_service
        
        # Initialize sub-components
        self.sheet_aligner = SheetAligner()
        self.difference_calculator = DifferenceCalculator()
        self.comparison_formatter = ComparisonFormatter(cache_service=cache_service)
        
        logger.info("ComparisonEngine initialized")
    
    def compare_files(
        self,
        file_ids: List[str],
        query: str,
        sheet_names: Optional[List[str]] = None
    ) -> ComparisonResult:
        """
        Compare data across multiple files.
        
        Args:
            file_ids: List of file IDs to compare (up to 5)
            query: The original user query for context
            sheet_names: Optional list of specific sheet names to compare
        
        Returns:
            ComparisonResult with aligned data, differences, and summary
        
        Raises:
            ValueError: If more than 5 files are provided or file_ids is empty
        """
        if not file_ids:
            raise ValueError("At least one file ID must be provided")
        
        if len(file_ids) > 5:
            logger.warning(f"Limiting comparison to first 5 files (received {len(file_ids)})")
            file_ids = file_ids[:5]
        
        logger.info(f"Starting comparison of {len(file_ids)} files")
        
        try:
            # Step 1: Retrieve and extract sheets from all files
            sheets_by_file = self._retrieve_sheets(file_ids, sheet_names)
            
            if not sheets_by_file:
                logger.warning("No sheets retrieved for comparison")
                return ComparisonResult(
                    files_compared=[],
                    aligned_data={},
                    differences={},
                    summary="No data found for comparison",
                    visualization_data=None
                )
            
            # Step 2: Align sheets across files
            aligned_data = self._align_sheets(sheets_by_file)
            
            # Step 3: Calculate differences
            differences = self._calculate_differences(aligned_data, sheets_by_file)
            
            # Step 4: Format results
            comparison_result = self._format_results(
                file_ids,
                sheets_by_file,
                aligned_data,
                differences,
                query
            )
            
            logger.info(f"Comparison completed successfully for {len(file_ids)} files")
            return comparison_result
            
        except Exception as e:
            logger.error(f"Error during file comparison: {str(e)}", exc_info=True)
            # Return a result with error information
            return ComparisonResult(
                files_compared=[],
                aligned_data={},
                differences={},
                summary=f"Error during comparison: {str(e)}",
                visualization_data=None
            )
    
    def _retrieve_sheets(
        self,
        file_ids: List[str],
        sheet_names: Optional[List[str]] = None
    ) -> Dict[str, List[SheetData]]:
        """
        Retrieve and extract sheets from multiple files.
        
        Args:
            file_ids: List of file IDs to retrieve
            sheet_names: Optional list of specific sheet names to extract
        
        Returns:
            Dictionary mapping file_id to list of SheetData objects
        """
        sheets_by_file = {}
        
        for file_id in file_ids:
            try:
                # Download file content
                file_content = self.gdrive_connector.download_file(file_id)
                file_metadata = self.gdrive_connector.get_file_metadata(file_id)
                
                # Extract workbook data
                workbook_data = self.content_extractor.extract_workbook(
                    file_content,
                    file_metadata.name
                )
                
                # Filter sheets if specific names provided
                if sheet_names:
                    filtered_sheets = [
                        sheet for sheet in workbook_data.sheets
                        if sheet.sheet_name in sheet_names
                    ]
                    sheets_by_file[file_id] = filtered_sheets
                else:
                    sheets_by_file[file_id] = workbook_data.sheets
                
                logger.info(
                    f"Retrieved {len(sheets_by_file[file_id])} sheets from file {file_metadata.name}"
                )
                
            except Exception as e:
                logger.error(f"Failed to retrieve sheets from file {file_id}: {str(e)}")
                # Continue with other files
                continue
        
        return sheets_by_file
    
    def _align_sheets(
        self,
        sheets_by_file: Dict[str, List[SheetData]]
    ) -> AlignedData:
        """
        Align sheets across files using the SheetAligner.
        
        Args:
            sheets_by_file: Dictionary mapping file_id to list of sheets
        
        Returns:
            AlignedData structure with column mappings and row alignments
        """
        # Collect all sheets for alignment
        all_sheets = []
        file_ids = []
        
        for file_id, sheets in sheets_by_file.items():
            for sheet in sheets:
                all_sheets.append(sheet)
                file_ids.append(file_id)
        
        if not all_sheets:
            return AlignedData(
                common_columns=[],
                file_data={},
                missing_columns={}
            )
        
        # Use SheetAligner to align the sheets
        aligned_data = self.sheet_aligner.align_sheets(all_sheets, file_ids)
        
        logger.info(
            f"Aligned {len(all_sheets)} sheets with {len(aligned_data.common_columns)} common columns"
        )
        
        return aligned_data
    
    def _calculate_differences(
        self,
        aligned_data: AlignedData,
        sheets_by_file: Dict[str, List[SheetData]]
    ) -> Dict[str, Any]:
        """
        Calculate differences using the DifferenceCalculator.
        
        Args:
            aligned_data: Aligned data structure
            sheets_by_file: Original sheets organized by file
        
        Returns:
            Dictionary containing calculated differences and trends
        """
        if not aligned_data.common_columns or not aligned_data.file_data:
            logger.warning("No common data to calculate differences")
            return {}
        
        # Use DifferenceCalculator to compute differences
        differences = self.difference_calculator.calculate_differences(aligned_data)
        
        logger.info(f"Calculated differences for {len(differences)} metrics")
        
        return differences
    
    def _format_results(
        self,
        file_ids: List[str],
        sheets_by_file: Dict[str, List[SheetData]],
        aligned_data: AlignedData,
        differences: Dict[str, Any],
        query: str
    ) -> ComparisonResult:
        """
        Format comparison results using the ComparisonFormatter.
        
        Args:
            file_ids: List of file IDs compared
            sheets_by_file: Original sheets organized by file
            aligned_data: Aligned data structure
            differences: Calculated differences
            query: Original user query
        
        Returns:
            Formatted ComparisonResult
        """
        # Get file names for the result
        file_names = []
        for file_id in file_ids:
            if file_id in sheets_by_file and sheets_by_file[file_id]:
                # Use the file name from the first sheet's parent file
                # (This is a simplification; in production, we'd track file names separately)
                file_names.append(file_id)
        
        # Use ComparisonFormatter to create the final result
        comparison_result = self.comparison_formatter.format_comparison(
            file_ids=file_ids,
            aligned_data=aligned_data,
            differences=differences,
            query=query
        )
        
        logger.info("Formatted comparison results")
        
        return comparison_result
