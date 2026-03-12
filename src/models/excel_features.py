"""
Excel-specific feature models for enhanced extraction.

This module defines the data models for Excel-specific features including:
- FormulaCell: Excel cells containing formulas with computed values
- MergedCellInfo: Information about merged cells and their ranges
- NamedRange: Excel named ranges with scope information
- ExcelTable: Excel Tables (ListObjects) with headers and metadata
- ConditionalFormat: Conditional formatting rules applied to cells
- DataValidation: Data validation rules for cells
- ExtractionWarning: Warnings generated during extraction
- EnhancedExtractionResult: Extended extraction result with all Excel features

These models support Requirements 18.1, 19.2, 20.1, 30.1, 32.1, 35.1.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.chunk_visibility import ExtractionMetadata


@dataclass
class FormulaCell:
    """
    Excel cell containing a formula.
    
    Captures both the formula text and the computed value for formula cells,
    enabling queries about both the formula logic and the resulting values.
    
    Attributes:
        cell_reference: Cell reference in A1 notation (e.g., "B5", "Sheet1!C10").
        formula_text: The formula text (e.g., "=SUM(A1:A10)").
        computed_value: The computed/cached value of the formula.
        has_error: Whether the formula has an error state.
        error_type: The error type if has_error is True (e.g., "#REF!", "#VALUE!",
            "#DIV/0!", "#NAME?", "#N/A", "#NULL!", "#NUM!").
        references_external: Whether the formula references external workbooks.
    
    Supports Requirement 18.1: Capture both formula text and computed value
    for formula cells.
    """
    cell_reference: str
    formula_text: str
    computed_value: Any
    has_error: bool
    error_type: Optional[str]
    references_external: bool
    
    # Valid Excel error types
    VALID_ERROR_TYPES = frozenset({
        "#REF!",
        "#VALUE!",
        "#DIV/0!",
        "#NAME?",
        "#N/A",
        "#NULL!",
        "#NUM!",
        "#GETTING_DATA",
        "#SPILL!",
        "#CALC!",
        "#BLOCKED!",
        "#UNKNOWN!",
        "#FIELD!",
        "#CONNECT!",
    })
    
    def __post_init__(self) -> None:
        """Validate formula cell data after initialization."""
        if not self.cell_reference:
            raise ValueError("cell_reference cannot be empty")
        if not self.formula_text:
            raise ValueError("formula_text cannot be empty")
        if not self.formula_text.startswith("="):
            raise ValueError(
                f"formula_text must start with '=', got '{self.formula_text[:10]}...'"
            )
        
        # Validate error_type consistency
        if self.has_error and not self.error_type:
            raise ValueError("error_type is required when has_error is True")
        if not self.has_error and self.error_type:
            raise ValueError("error_type should be None when has_error is False")
        
        # Validate error_type is a known Excel error
        if self.error_type and self.error_type not in self.VALID_ERROR_TYPES:
            raise ValueError(
                f"error_type must be one of {sorted(self.VALID_ERROR_TYPES)}, "
                f"got '{self.error_type}'"
            )


@dataclass
class MergedCellInfo:
    """
    Information about merged cells in an Excel worksheet.
    
    Tracks merged cell ranges and their values to enable proper data
    extraction and display of merged cell information.
    
    Attributes:
        merge_range: The cell range of the merge in A1 notation (e.g., "A1:C1").
        value: The value contained in the merged cell.
        rows_spanned: Number of rows the merge spans (minimum 1).
        cols_spanned: Number of columns the merge spans (minimum 1).
    
    Supports Requirement 30.1: Detect merged cells and their ranges.
    """
    merge_range: str
    value: Any
    rows_spanned: int
    cols_spanned: int
    
    def __post_init__(self) -> None:
        """Validate merged cell info after initialization."""
        if not self.merge_range:
            raise ValueError("merge_range cannot be empty")
        
        # Validate merge_range format (should contain ':' for a range)
        if ":" not in self.merge_range:
            raise ValueError(
                f"merge_range must be a range (e.g., 'A1:C1'), got '{self.merge_range}'"
            )
        
        if self.rows_spanned < 1:
            raise ValueError(
                f"rows_spanned must be at least 1, got {self.rows_spanned}"
            )
        if self.cols_spanned < 1:
            raise ValueError(
                f"cols_spanned must be at least 1, got {self.cols_spanned}"
            )
        
        # A merge must span more than one cell
        if self.rows_spanned == 1 and self.cols_spanned == 1:
            raise ValueError(
                "A merged cell must span more than one cell "
                "(rows_spanned > 1 or cols_spanned > 1)"
            )
    
    @property
    def total_cells(self) -> int:
        """
        Calculate the total number of cells in the merge.
        
        Returns:
            Total number of cells covered by the merge.
        """
        return self.rows_spanned * self.cols_spanned


@dataclass
class NamedRange:
    """
    Excel named range definition.
    
    Represents a named range in an Excel workbook, which can be either
    workbook-scoped or sheet-scoped.
    
    Attributes:
        name: The name of the named range.
        cell_range: The cell range the name refers to (e.g., "A1:B10").
        sheet_name: The sheet name if the range is on a specific sheet,
            or None for workbook-level names.
        scope: The scope of the named range ("workbook" or "sheet").
    
    Supports Requirement 32.1: Detect and index Excel named ranges with
    their names and cell references.
    """
    name: str
    cell_range: str
    sheet_name: Optional[str]
    scope: str
    
    VALID_SCOPES = frozenset({"workbook", "sheet"})
    
    def __post_init__(self) -> None:
        """Validate named range data after initialization."""
        if not self.name:
            raise ValueError("name cannot be empty")
        if not self.cell_range:
            raise ValueError("cell_range cannot be empty")
        
        if self.scope not in self.VALID_SCOPES:
            raise ValueError(
                f"scope must be one of {sorted(self.VALID_SCOPES)}, got '{self.scope}'"
            )
        
        # If scope is "sheet", sheet_name should be provided
        if self.scope == "sheet" and not self.sheet_name:
            raise ValueError("sheet_name is required when scope is 'sheet'")
    
    @property
    def full_reference(self) -> str:
        """
        Get the full reference including sheet name if applicable.
        
        Returns:
            Full reference string (e.g., "Sheet1!A1:B10" or "A1:B10").
        """
        if self.sheet_name:
            return f"{self.sheet_name}!{self.cell_range}"
        return self.cell_range


@dataclass
class ExcelTable:
    """
    Excel Table (ListObject) definition.
    
    Represents an Excel Table with its name, location, headers, and size.
    Excel Tables provide structured references and automatic formatting.
    
    Attributes:
        name: The name of the Excel Table.
        cell_range: The cell range of the table (e.g., "A1:D100").
        sheet_name: The name of the sheet containing the table.
        headers: List of column header names in the table.
        row_count: Number of data rows in the table (excluding header).
    
    Supports Requirement 32.1: Detect Excel Tables (ListObjects) and index
    them with their table names and column headers.
    """
    name: str
    cell_range: str
    sheet_name: str
    headers: list[str]
    row_count: int
    
    def __post_init__(self) -> None:
        """Validate Excel table data after initialization."""
        if not self.name:
            raise ValueError("name cannot be empty")
        if not self.cell_range:
            raise ValueError("cell_range cannot be empty")
        if not self.sheet_name:
            raise ValueError("sheet_name cannot be empty")
        if not self.headers:
            raise ValueError("headers cannot be empty")
        if self.row_count < 0:
            raise ValueError(f"row_count must be non-negative, got {self.row_count}")
    
    @property
    def column_count(self) -> int:
        """
        Get the number of columns in the table.
        
        Returns:
            Number of columns based on headers.
        """
        return len(self.headers)


@dataclass
class ConditionalFormat:
    """
    Conditional formatting rule applied to cells.
    
    Represents a conditional formatting rule that changes cell appearance
    based on cell values or formulas.
    
    Attributes:
        cell_range: The cell range the formatting applies to (e.g., "A1:A100").
        rule_type: The type of conditional formatting rule (e.g., "cellIs",
            "colorScale", "dataBar", "iconSet", "top10", "aboveAverage",
            "duplicateValues", "expression").
        formula: The formula used in the rule, if applicable.
        format_description: Human-readable description of the format
            (e.g., "Red fill if < 0", "Green text if > 100").
    
    Supports Requirement 35.1: Detect cells with conditional formatting
    and store the formatting rules.
    """
    cell_range: str
    rule_type: str
    formula: Optional[str]
    format_description: str
    
    VALID_RULE_TYPES = frozenset({
        "cellIs",
        "colorScale",
        "dataBar",
        "iconSet",
        "top10",
        "aboveAverage",
        "belowAverage",
        "duplicateValues",
        "uniqueValues",
        "expression",
        "containsText",
        "notContainsText",
        "beginsWith",
        "endsWith",
        "containsBlanks",
        "notContainsBlanks",
        "containsErrors",
        "notContainsErrors",
        "timePeriod",
    })
    
    def __post_init__(self) -> None:
        """Validate conditional format data after initialization."""
        if not self.cell_range:
            raise ValueError("cell_range cannot be empty")
        if not self.rule_type:
            raise ValueError("rule_type cannot be empty")
        if not self.format_description:
            raise ValueError("format_description cannot be empty")
        
        if self.rule_type not in self.VALID_RULE_TYPES:
            raise ValueError(
                f"rule_type must be one of {sorted(self.VALID_RULE_TYPES)}, "
                f"got '{self.rule_type}'"
            )


@dataclass
class DataValidation:
    """
    Data validation rule applied to cells.
    
    Represents a data validation rule that restricts the values that
    can be entered into cells.
    
    Attributes:
        cell_range: The cell range the validation applies to (e.g., "B2:B100").
        validation_type: The type of validation (e.g., "list", "whole",
            "decimal", "date", "time", "textLength", "custom").
        allowed_values: List of allowed values for "list" type validation.
        formula: The formula used for validation, if applicable.
        error_message: The error message shown when validation fails.
    
    Supports Requirement 35.1: Detect data validation rules (dropdowns,
    ranges) and store allowed values.
    """
    cell_range: str
    validation_type: str
    allowed_values: Optional[list[str]]
    formula: Optional[str]
    error_message: Optional[str]
    
    VALID_VALIDATION_TYPES = frozenset({
        "list",
        "whole",
        "decimal",
        "date",
        "time",
        "textLength",
        "custom",
    })
    
    def __post_init__(self) -> None:
        """Validate data validation rule after initialization."""
        if not self.cell_range:
            raise ValueError("cell_range cannot be empty")
        if not self.validation_type:
            raise ValueError("validation_type cannot be empty")
        
        if self.validation_type not in self.VALID_VALIDATION_TYPES:
            raise ValueError(
                f"validation_type must be one of {sorted(self.VALID_VALIDATION_TYPES)}, "
                f"got '{self.validation_type}'"
            )
        
        # For list type, allowed_values should be provided
        if self.validation_type == "list" and not self.allowed_values:
            raise ValueError(
                "allowed_values is required when validation_type is 'list'"
            )


@dataclass
class ExtractionWarning:
    """
    Warning generated during Excel data extraction.
    
    Represents a warning or issue encountered during the extraction
    process that doesn't prevent extraction but may affect data quality.
    
    Attributes:
        warning_type: The type of warning (e.g., "formula_error",
            "external_reference", "unsupported_feature", "data_truncation",
            "encoding_issue", "corrupted_cell").
        message: Human-readable description of the warning.
        location: The location in the file where the warning occurred
            (e.g., "Sheet1!A1:C10"), or None if not location-specific.
        severity: The severity level ("info", "warning", "error").
    
    Supports extraction quality tracking and debugging.
    """
    warning_type: str
    message: str
    location: Optional[str]
    severity: str
    
    VALID_WARNING_TYPES = frozenset({
        "formula_error",
        "external_reference",
        "unsupported_feature",
        "data_truncation",
        "encoding_issue",
        "corrupted_cell",
        "missing_data",
        "format_issue",
        "pivot_table_issue",
        "chart_issue",
        "macro_detected",
        "password_protected",
        "large_file",
        "complex_structure",
    })
    
    VALID_SEVERITIES = frozenset({"info", "warning", "error"})
    
    def __post_init__(self) -> None:
        """Validate extraction warning after initialization."""
        if not self.warning_type:
            raise ValueError("warning_type cannot be empty")
        if not self.message:
            raise ValueError("message cannot be empty")
        if not self.severity:
            raise ValueError("severity cannot be empty")
        
        if self.warning_type not in self.VALID_WARNING_TYPES:
            raise ValueError(
                f"warning_type must be one of {sorted(self.VALID_WARNING_TYPES)}, "
                f"got '{self.warning_type}'"
            )
        
        if self.severity not in self.VALID_SEVERITIES:
            raise ValueError(
                f"severity must be one of {sorted(self.VALID_SEVERITIES)}, "
                f"got '{self.severity}'"
            )


@dataclass
class PivotTableInfo:
    """
    Pivot table metadata and structure for extraction.
    
    Represents a pivot table detected in an Excel file with its
    configuration and source information. This is used during extraction
    processing, distinct from PivotTableData in domain_models.py which
    is used for API responses.
    
    Attributes:
        name: The name of the pivot table.
        sheet_name: The sheet containing the pivot table.
        location: The cell range where the pivot table is located.
        source_range: The source data range for the pivot table.
        row_fields: List of field names used as row labels.
        column_fields: List of field names used as column labels.
        value_fields: List of field names used as values (with aggregation).
        filters: List of field names used as report filters.
    
    Supports Requirement 19.2: Display pivot table metadata including
    source range, row fields, column fields, value fields, filters.
    """
    name: str
    sheet_name: str
    location: str
    source_range: Optional[str]
    row_fields: list[str] = field(default_factory=list)
    column_fields: list[str] = field(default_factory=list)
    value_fields: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Validate pivot table data after initialization."""
        if not self.name:
            raise ValueError("name cannot be empty")
        if not self.sheet_name:
            raise ValueError("sheet_name cannot be empty")
        if not self.location:
            raise ValueError("location cannot be empty")


@dataclass
class ChartInfo:
    """
    Chart metadata and underlying data series for extraction.
    
    Represents a chart detected in an Excel file with its type,
    configuration, and data series information. This is used during
    extraction processing, distinct from ChartData in domain_models.py
    which is used for API responses.
    
    Attributes:
        chart_type: The type of chart (e.g., "bar", "line", "pie", "scatter").
        title: The chart title, if set.
        sheet_name: The sheet containing the chart.
        location: The anchor cell or position of the chart.
        axis_labels: Dictionary of axis labels (e.g., {"x": "Month", "y": "Sales"}).
        data_series: List of data series names in the chart.
        source_ranges: List of cell ranges used as data sources.
    
    Supports Requirement 20.1: Detect charts and extract underlying data series.
    """
    chart_type: str
    title: Optional[str]
    sheet_name: str
    location: str
    axis_labels: dict[str, str] = field(default_factory=dict)
    data_series: list[str] = field(default_factory=list)
    source_ranges: list[str] = field(default_factory=list)
    
    VALID_CHART_TYPES = frozenset({
        "bar",
        "barStacked",
        "bar3D",
        "column",
        "columnStacked",
        "column3D",
        "line",
        "lineStacked",
        "line3D",
        "pie",
        "pie3D",
        "doughnut",
        "scatter",
        "bubble",
        "area",
        "areaStacked",
        "area3D",
        "radar",
        "surface",
        "stock",
        "combo",
        "unknown",
    })
    
    def __post_init__(self) -> None:
        """Validate chart data after initialization."""
        if not self.chart_type:
            raise ValueError("chart_type cannot be empty")
        if not self.sheet_name:
            raise ValueError("sheet_name cannot be empty")
        if not self.location:
            raise ValueError("location cannot be empty")
        
        if self.chart_type not in self.VALID_CHART_TYPES:
            raise ValueError(
                f"chart_type must be one of {sorted(self.VALID_CHART_TYPES)}, "
                f"got '{self.chart_type}'"
            )


@dataclass
class ExtractedSheetData:
    """
    Extracted data from a single Excel sheet for internal processing.
    
    Contains the raw data and metadata for a worksheet. This is used
    during extraction processing, distinct from SheetData in domain_models.py
    which is used for API responses.
    
    Attributes:
        sheet_name: Name of the worksheet.
        headers: List of column headers detected.
        data: List of rows, where each row is a list of cell values.
        row_count: Total number of data rows (excluding header).
        column_count: Total number of columns.
        has_headers: Whether headers were detected.
    """
    sheet_name: str
    headers: list[str]
    data: list[list[Any]]
    row_count: int
    column_count: int
    has_headers: bool
    
    def __post_init__(self) -> None:
        """Validate sheet data after initialization."""
        if not self.sheet_name:
            raise ValueError("sheet_name cannot be empty")
        if self.row_count < 0:
            raise ValueError(f"row_count must be non-negative, got {self.row_count}")
        if self.column_count < 0:
            raise ValueError(
                f"column_count must be non-negative, got {self.column_count}"
            )


@dataclass
class ExtractionQuality:
    """
    Quality metrics for an extraction result.
    
    Provides scores and indicators for the quality of extracted data.
    
    Attributes:
        score: Overall quality score (0.0 to 1.0).
        data_completeness: Completeness of extracted data (0.0 to 1.0).
        structure_clarity: Clarity of data structure (0.0 to 1.0).
        has_headers: Whether headers were detected.
        has_data: Whether actual data rows were found.
        error_count: Number of errors encountered during extraction.
        warning_count: Number of warnings generated during extraction.
    """
    score: float
    data_completeness: float
    structure_clarity: float
    has_headers: bool
    has_data: bool
    error_count: int
    warning_count: int
    
    def __post_init__(self) -> None:
        """Validate quality metrics after initialization."""
        for field_name in ["score", "data_completeness", "structure_clarity"]:
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{field_name} must be between 0.0 and 1.0, got {value}"
                )
        
        if self.error_count < 0:
            raise ValueError(
                f"error_count must be non-negative, got {self.error_count}"
            )
        if self.warning_count < 0:
            raise ValueError(
                f"warning_count must be non-negative, got {self.warning_count}"
            )


@dataclass
class EnhancedExtractionResult:
    """
    Extended extraction result with Excel-specific data.
    
    Contains the complete extraction result including base sheet data,
    quality metrics, and all Excel-specific features like formulas,
    pivot tables, charts, merged cells, named ranges, and more.
    
    Attributes:
        sheets: List of extracted sheet data.
        quality: Quality metrics for the extraction.
        formula_cells: List of formula cells detected.
        pivot_tables: List of pivot tables detected.
        charts: List of charts detected.
        merged_cells: List of merged cell ranges.
        named_ranges: List of named ranges.
        excel_tables: List of Excel Tables (ListObjects).
        hidden_sheets: List of hidden sheet names.
        hidden_rows: Dictionary mapping sheet names to lists of hidden row indices.
        hidden_columns: Dictionary mapping sheet names to lists of hidden column letters.
        conditional_formatting: List of conditional formatting rules.
        data_validations: List of data validation rules.
        warnings: List of extraction warnings.
        detected_language: Primary language detected in the content.
        detected_units: List of units detected (e.g., "$", "€", "%", "kg").
        detected_currencies: List of currencies detected (e.g., "USD", "EUR").
        date_columns: Dictionary mapping sheet names to lists of date column names.
    
    Supports Requirements 18.1, 19.2, 20.1, 30.1, 32.1, 35.1.
    """
    # Base extraction
    sheets: list[ExtractedSheetData]
    quality: ExtractionQuality
    
    # Excel-specific features
    formula_cells: list[FormulaCell] = field(default_factory=list)
    pivot_tables: list[PivotTableInfo] = field(default_factory=list)
    charts: list[ChartInfo] = field(default_factory=list)
    merged_cells: list[MergedCellInfo] = field(default_factory=list)
    named_ranges: list[NamedRange] = field(default_factory=list)
    excel_tables: list[ExcelTable] = field(default_factory=list)
    hidden_sheets: list[str] = field(default_factory=list)
    hidden_rows: dict[str, list[int]] = field(default_factory=dict)
    hidden_columns: dict[str, list[str]] = field(default_factory=dict)
    conditional_formatting: list[ConditionalFormat] = field(default_factory=list)
    data_validations: list[DataValidation] = field(default_factory=list)
    warnings: list[ExtractionWarning] = field(default_factory=list)
    
    # Metadata
    detected_language: str = "en"
    detected_units: list[str] = field(default_factory=list)
    detected_currencies: list[str] = field(default_factory=list)
    date_columns: dict[str, list[str]] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Validate enhanced extraction result after initialization."""
        if not self.sheets:
            raise ValueError("sheets cannot be empty")
        if not self.detected_language:
            raise ValueError("detected_language cannot be empty")
    
    @property
    def total_rows(self) -> int:
        """
        Calculate total rows across all sheets.
        
        Returns:
            Total number of data rows.
        """
        return sum(sheet.row_count for sheet in self.sheets)
    
    @property
    def sheet_names(self) -> list[str]:
        """
        Get list of all sheet names.
        
        Returns:
            List of sheet names.
        """
        return [sheet.sheet_name for sheet in self.sheets]
    
    @property
    def has_formulas(self) -> bool:
        """
        Check if any formula cells were detected.
        
        Returns:
            True if formula cells exist.
        """
        return len(self.formula_cells) > 0
    
    @property
    def has_pivot_tables(self) -> bool:
        """
        Check if any pivot tables were detected.
        
        Returns:
            True if pivot tables exist.
        """
        return len(self.pivot_tables) > 0
    
    @property
    def has_charts(self) -> bool:
        """
        Check if any charts were detected.
        
        Returns:
            True if charts exist.
        """
        return len(self.charts) > 0
    
    @property
    def has_merged_cells(self) -> bool:
        """
        Check if any merged cells were detected.
        
        Returns:
            True if merged cells exist.
        """
        return len(self.merged_cells) > 0
    
    @property
    def has_hidden_content(self) -> bool:
        """
        Check if any hidden content was detected.
        
        Returns:
            True if hidden sheets, rows, or columns exist.
        """
        return (
            len(self.hidden_sheets) > 0
            or any(rows for rows in self.hidden_rows.values())
            or any(cols for cols in self.hidden_columns.values())
        )
    
    @property
    def error_warnings(self) -> list[ExtractionWarning]:
        """
        Get only error-level warnings.
        
        Returns:
            List of warnings with severity "error".
        """
        return [w for w in self.warnings if w.severity == "error"]
    
    def get_sheet(self, sheet_name: str) -> Optional[ExtractedSheetData]:
        """
        Get sheet data by name.
        
        Args:
            sheet_name: Name of the sheet to retrieve.
            
        Returns:
            ExtractedSheetData if found, None otherwise.
        """
        for sheet in self.sheets:
            if sheet.sheet_name == sheet_name:
                return sheet
        return None
    
    def get_formulas_for_sheet(self, sheet_name: str) -> list[FormulaCell]:
        """
        Get formula cells for a specific sheet.
        
        Args:
            sheet_name: Name of the sheet.
            
        Returns:
            List of formula cells in the sheet.
        """
        return [
            fc for fc in self.formula_cells
            if fc.cell_reference.startswith(f"{sheet_name}!")
            or (
                "!" not in fc.cell_reference
                and len(self.sheets) == 1
                and self.sheets[0].sheet_name == sheet_name
            )
        ]
    
    def get_merged_cells_for_sheet(self, sheet_name: str) -> list[MergedCellInfo]:
        """
        Get merged cells for a specific sheet.
        
        Note: MergedCellInfo doesn't include sheet name, so this method
        requires the caller to track which sheet the merged cells belong to.
        For multi-sheet workbooks, consider using sheet-prefixed ranges.
        
        Args:
            sheet_name: Name of the sheet.
            
        Returns:
            List of merged cells (filtering not implemented without sheet tracking).
        """
        # MergedCellInfo doesn't track sheet name, return all for now
        # In practice, merged cells should be tracked per-sheet during extraction
        return self.merged_cells

