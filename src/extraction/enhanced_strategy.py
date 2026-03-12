"""
Enhanced extraction strategy abstract base class.

This module defines the abstract base class for enhanced Excel extraction
strategies that support Excel-specific features like formulas, pivot tables,
charts, merged cells, named ranges, and hidden content.

Supports Requirements:
- 18.1: Capture both formula text and computed value for formula cells
- 19.1: Detect pivot tables and extract their data separately
- 20.1: Detect charts and extract underlying data series
- 30.1: Detect merged cells and their ranges
- 31.1: Detect hidden rows, columns, and sheets
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from src.extraction.extraction_strategy import ExtractionConfig
from src.models.excel_features import (
    ChartInfo,
    EnhancedExtractionResult,
    ExcelTable,
    FormulaCell,
    MergedCellInfo,
    NamedRange,
    PivotTableInfo,
)


class EnhancedExtractionStrategy(ABC):
    """
    Abstract base class for enhanced Excel extraction strategies.
    
    Extends base extraction with Excel-specific feature detection including
    formulas, pivot tables, charts, merged cells, named ranges, and hidden
    content. All implementations must follow the Dependency Inversion
    Principle with dependencies injected via constructor.
    
    This class defines the contract for extractors that need to handle
    complex Excel features beyond basic cell data extraction.
    
    Attributes:
        config: Extraction configuration settings injected at construction.
    
    Example:
        >>> class MyExtractor(EnhancedExtractionStrategy):
        ...     def __init__(self, config: ExtractionConfig):
        ...         self._config = config
        ...     # ... implement all abstract methods
    """
    
    @abstractmethod
    def extract(
        self,
        file_path: str,
        config: Optional[ExtractionConfig] = None
    ) -> EnhancedExtractionResult:
        """
        Extract data from an Excel file with full feature support.
        
        Performs comprehensive extraction including sheet data, formulas,
        pivot tables, charts, merged cells, named ranges, and hidden content.
        
        Args:
            file_path: Path to the Excel file to extract.
            config: Optional extraction configuration. If not provided,
                uses the configuration injected at construction.
        
        Returns:
            EnhancedExtractionResult containing all extracted data and
            Excel-specific features.
        
        Raises:
            ExtractionError: If extraction fails due to file access,
                corruption, or unsupported format.
            ConfigurationError: If required configuration is missing.
        
        Supports Requirement 18.1, 19.1, 20.1, 30.1, 31.1.
        """
        ...
    
    @abstractmethod
    def detect_formulas(self, workbook: Any) -> list[FormulaCell]:
        """
        Detect and extract formula cells from a workbook.
        
        Scans all sheets in the workbook to identify cells containing
        formulas, capturing both the formula text and computed value.
        
        Args:
            workbook: The workbook object to scan. The type depends on
                the underlying library (e.g., openpyxl.Workbook).
        
        Returns:
            List of FormulaCell objects containing cell reference,
            formula text, computed value, error state, and external
            reference indicators.
        
        Supports Requirement 18.1: Capture both formula text and computed
        value for formula cells.
        """
        ...
    
    @abstractmethod
    def detect_merged_cells(self, workbook: Any) -> list[MergedCellInfo]:
        """
        Detect merged cells and their ranges in a workbook.
        
        Identifies all merged cell regions across all sheets, capturing
        the merge range, value, and span dimensions.
        
        Args:
            workbook: The workbook object to scan. The type depends on
                the underlying library (e.g., openpyxl.Workbook).
        
        Returns:
            List of MergedCellInfo objects containing merge range,
            value, rows spanned, and columns spanned.
        
        Supports Requirement 30.1: Detect merged cells and their ranges.
        """
        ...
    
    @abstractmethod
    def detect_named_ranges(self, workbook: Any) -> list[NamedRange]:
        """
        Detect named ranges defined in a workbook.
        
        Identifies all named ranges including workbook-scoped and
        sheet-scoped definitions.
        
        Args:
            workbook: The workbook object to scan. The type depends on
                the underlying library (e.g., openpyxl.Workbook).
        
        Returns:
            List of NamedRange objects containing name, cell range,
            sheet name (if sheet-scoped), and scope indicator.
        """
        ...
    
    @abstractmethod
    def detect_excel_tables(self, workbook: Any) -> list[ExcelTable]:
        """
        Detect Excel Tables (ListObjects) in a workbook.
        
        Identifies all structured tables defined in the workbook,
        capturing table name, range, headers, and row count.
        
        Args:
            workbook: The workbook object to scan. The type depends on
                the underlying library (e.g., openpyxl.Workbook).
        
        Returns:
            List of ExcelTable objects containing table name, cell range,
            sheet name, headers, and row count.
        """
        ...
    
    @abstractmethod
    def detect_pivot_tables(self, workbook: Any) -> list[PivotTableInfo]:
        """
        Detect pivot tables in a workbook.
        
        Identifies all pivot tables and extracts their metadata including
        source range, field configurations, and filters.
        
        Args:
            workbook: The workbook object to scan. The type depends on
                the underlying library (e.g., openpyxl.Workbook).
        
        Returns:
            List of PivotTableInfo objects containing pivot table name,
            location, source range, row/column/value fields, and filters.
        
        Supports Requirement 19.1: Detect pivot tables and extract their
        data separately.
        """
        ...
    
    @abstractmethod
    def detect_charts(self, workbook: Any) -> list[ChartInfo]:
        """
        Detect charts and extract underlying data series.
        
        Identifies all charts in the workbook and extracts their type,
        title, axis labels, data series, and source ranges.
        
        Args:
            workbook: The workbook object to scan. The type depends on
                the underlying library (e.g., openpyxl.Workbook).
        
        Returns:
            List of ChartInfo objects containing chart type, title,
            sheet name, location, axis labels, data series names,
            and source ranges.
        
        Supports Requirement 20.1: Detect charts and extract underlying
        data series.
        """
        ...
    
    @abstractmethod
    def detect_hidden_content(
        self,
        workbook: Any
    ) -> tuple[list[str], dict[str, list[int]], dict[str, list[str]]]:
        """
        Detect hidden sheets, rows, and columns in a workbook.
        
        Identifies all hidden content including hidden sheets, hidden
        rows per sheet, and hidden columns per sheet.
        
        Args:
            workbook: The workbook object to scan. The type depends on
                the underlying library (e.g., openpyxl.Workbook).
        
        Returns:
            A tuple containing:
            - hidden_sheets: List of hidden sheet names.
            - hidden_rows: Dictionary mapping sheet names to lists of
              hidden row indices (1-indexed).
            - hidden_columns: Dictionary mapping sheet names to lists of
              hidden column letters (e.g., "A", "B", "AA").
        
        Supports Requirement 31.1: Detect hidden rows, columns, and sheets.
        """
        ...
