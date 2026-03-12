"""
Core domain models for the Google Drive Excel RAG system.

This module defines Pydantic models for all core domain objects including
file metadata, sheet data, workbook data, cell data, pivot tables, charts,
and query-related models.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class FileStatus(str, Enum):
    """Status of a file in the indexing system."""
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class DataType(str, Enum):
    """Data types found in Excel cells."""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    FORMULA = "formula"
    EMPTY = "empty"


class FileMetadata(BaseModel):
    """Metadata for an Excel file from Google Drive."""
    file_id: str = Field(..., description="Google Drive file ID")
    name: str = Field(..., description="File name")
    path: str = Field(..., description="Full path in Google Drive")
    mime_type: str = Field(..., description="MIME type of the file")
    size: int = Field(..., ge=0, description="File size in bytes")
    modified_time: datetime = Field(..., description="Last modified timestamp")
    md5_checksum: str = Field(..., description="MD5 checksum for change detection")
    status: FileStatus = Field(default=FileStatus.PENDING, description="Indexing status")
    indexed_at: Optional[datetime] = Field(default=None, description="When file was indexed")

    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "1abc123def456",
                "name": "Expenses_Jan2024.xlsx",
                "path": "/Finance/2024/Expenses_Jan2024.xlsx",
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "size": 52480,
                "modified_time": "2024-01-15T10:30:00Z",
                "md5_checksum": "5d41402abc4b2a76b9719d911017c592",
                "status": "indexed",
                "indexed_at": "2024-01-16T08:00:00Z"
            }
        }


class CellData(BaseModel):
    """Data for a single Excel cell."""
    value: Any = Field(..., description="The calculated/displayed value")
    data_type: DataType = Field(..., description="Type of data in the cell")
    formula: Optional[str] = Field(default=None, description="Formula text if cell contains formula")
    formula_error: Optional[str] = Field(default=None, description="Error type if formula failed")
    format: Optional[str] = Field(default=None, description="Excel number format")
    is_formula: bool = Field(default=False, description="Whether cell contains a formula")

    class Config:
        json_schema_extra = {
            "example": {
                "value": 1500.50,
                "data_type": "number",
                "formula": "=SUM(B2:B9)",
                "formula_error": None,
                "format": "$#,##0.00",
                "is_formula": True
            }
        }


class PivotTableData(BaseModel):
    """Data for an Excel pivot table."""
    name: str = Field(..., description="Pivot table name")
    location: str = Field(..., description="Cell range where pivot table is located")
    source_range: str = Field(..., description="Source data range")
    row_fields: List[str] = Field(default_factory=list, description="Row grouping fields")
    column_fields: List[str] = Field(default_factory=list, description="Column grouping fields")
    data_fields: List[str] = Field(default_factory=list, description="Aggregated data fields")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Applied filters")
    aggregated_data: Dict[str, Any] = Field(default_factory=dict, description="Pivot results")
    summary: str = Field(..., description="Natural language description")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "PivotTable1",
                "location": "A1:D10",
                "source_range": "Sheet1!A1:F100",
                "row_fields": ["Region", "Product"],
                "column_fields": ["Month"],
                "data_fields": ["Sum of Sales", "Average of Price"],
                "filters": {"Year": "2024"},
                "aggregated_data": {},
                "summary": "Pivot table showing Sum of Sales grouped by Region and Product across months"
            }
        }


class ChartData(BaseModel):
    """Data for an Excel chart."""
    name: str = Field(..., description="Chart name")
    chart_type: str = Field(..., description="Type of chart (bar, line, pie, etc.)")
    title: Optional[str] = Field(default=None, description="Chart title")
    source_range: str = Field(..., description="Data range used for chart")
    series: List[Dict[str, Any]] = Field(default_factory=list, description="Chart series information")
    x_axis_label: Optional[str] = Field(default=None, description="X-axis label")
    y_axis_label: Optional[str] = Field(default=None, description="Y-axis label")
    summary: str = Field(..., description="Natural language description")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Chart1",
                "chart_type": "bar",
                "title": "Monthly Revenue",
                "source_range": "A1:B13",
                "series": [{"name": "Revenue", "values": "B2:B13"}],
                "x_axis_label": "Month",
                "y_axis_label": "Revenue ($)",
                "summary": "Bar chart titled 'Monthly Revenue' showing revenue by month from Jan to Dec"
            }
        }


class SheetData(BaseModel):
    """Data for a single Excel sheet."""
    sheet_name: str = Field(..., description="Name of the sheet")
    headers: List[str] = Field(default_factory=list, description="Column headers")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="Row data")
    data_types: Dict[str, DataType] = Field(default_factory=dict, description="Data type for each column")
    row_count: int = Field(..., ge=0, description="Number of rows")
    column_count: int = Field(..., ge=0, description="Number of columns")
    summary: str = Field(..., description="Natural language description of sheet")
    has_dates: bool = Field(default=False, description="Whether sheet contains date values")
    has_numbers: bool = Field(default=False, description="Whether sheet contains numeric values")
    pivot_tables: List[PivotTableData] = Field(default_factory=list, description="Pivot tables in sheet")
    charts: List[ChartData] = Field(default_factory=list, description="Charts in sheet")
    has_pivot_tables: bool = Field(default=False, description="Whether sheet has pivot tables")
    has_charts: bool = Field(default=False, description="Whether sheet has charts")
    llm_summary: Optional[str] = Field(default=None, description="LLM-generated semantic summary of sheet purpose")
    summary_generated_at: Optional[datetime] = Field(default=None, description="When LLM summary was generated")

    def model_post_init(self, __context):
        """Set flags after model initialization."""
        if self.pivot_tables and not self.has_pivot_tables:
            self.has_pivot_tables = len(self.pivot_tables) > 0
        if self.charts and not self.has_charts:
            self.has_charts = len(self.charts) > 0

    class Config:
        json_schema_extra = {
            "example": {
                "sheet_name": "Summary",
                "headers": ["Month", "Revenue", "Expenses", "Profit"],
                "rows": [
                    {"Month": "January", "Revenue": 10000, "Expenses": 7000, "Profit": 3000}
                ],
                "data_types": {"Month": "text", "Revenue": "number", "Expenses": "number", "Profit": "number"},
                "row_count": 12,
                "column_count": 4,
                "summary": "Monthly financial summary with revenue, expenses, and profit",
                "has_dates": False,
                "has_numbers": True,
                "pivot_tables": [],
                "charts": [],
                "has_pivot_tables": False,
                "has_charts": False
            }
        }


class WorkbookData(BaseModel):
    """Data for an entire Excel workbook."""
    file_id: str = Field(..., description="Google Drive file ID")
    file_name: str = Field(..., description="File name")
    file_path: str = Field(..., description="Full path in Google Drive")
    sheets: List[SheetData] = Field(default_factory=list, description="All sheets in workbook")
    modified_time: datetime = Field(..., description="Last modified timestamp")
    has_pivot_tables: bool = Field(default=False, description="Whether workbook has any pivot tables")
    has_charts: bool = Field(default=False, description="Whether workbook has any charts")
    total_pivot_tables: int = Field(default=0, ge=0, description="Total number of pivot tables")
    total_charts: int = Field(default=0, ge=0, description="Total number of charts")

    def model_post_init(self, __context):
        """Set aggregated flags and counts after model initialization."""
        if self.sheets:
            # Ensure sheet flags are set first
            for sheet in self.sheets:
                if sheet.pivot_tables and not sheet.has_pivot_tables:
                    sheet.has_pivot_tables = len(sheet.pivot_tables) > 0
                if sheet.charts and not sheet.has_charts:
                    sheet.has_charts = len(sheet.charts) > 0
            
            # Set workbook-level flags
            if not self.has_pivot_tables:
                self.has_pivot_tables = any(sheet.has_pivot_tables for sheet in self.sheets)
            if not self.has_charts:
                self.has_charts = any(sheet.has_charts for sheet in self.sheets)
            if self.total_pivot_tables == 0:
                self.total_pivot_tables = sum(len(sheet.pivot_tables) for sheet in self.sheets)
            if self.total_charts == 0:
                self.total_charts = sum(len(sheet.charts) for sheet in self.sheets)

    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "1abc123def456",
                "file_name": "Expenses_Jan2024.xlsx",
                "file_path": "/Finance/2024/Expenses_Jan2024.xlsx",
                "sheets": [],
                "modified_time": "2024-01-15T10:30:00Z",
                "has_pivot_tables": False,
                "has_charts": False,
                "total_pivot_tables": 0,
                "total_charts": 0
            }
        }


class RankedFile(BaseModel):
    """A file ranked by relevance to a query."""
    file_metadata: FileMetadata = Field(..., description="File metadata")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Overall relevance score")
    semantic_score: float = Field(..., ge=0.0, le=1.0, description="Semantic similarity score")
    metadata_score: float = Field(..., ge=0.0, le=1.0, description="Metadata match score")
    preference_score: float = Field(..., ge=0.0, le=1.0, description="User preference score")

    class Config:
        json_schema_extra = {
            "example": {
                "file_metadata": {
                    "file_id": "1abc123def456",
                    "name": "Expenses_Jan2024.xlsx",
                    "path": "/Finance/2024/Expenses_Jan2024.xlsx",
                    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "size": 52480,
                    "modified_time": "2024-01-15T10:30:00Z",
                    "md5_checksum": "5d41402abc4b2a76b9719d911017c592",
                    "status": "indexed"
                },
                "relevance_score": 0.92,
                "semantic_score": 0.95,
                "metadata_score": 0.88,
                "preference_score": 0.90
            }
        }


class SheetSelection(BaseModel):
    """Result of sheet selection process."""
    sheet_name: str = Field(..., description="Selected sheet name")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    requires_clarification: bool = Field(default=False, description="Whether clarification is needed")

    class Config:
        json_schema_extra = {
            "example": {
                "sheet_name": "Summary",
                "relevance_score": 0.87,
                "requires_clarification": False
            }
        }


class RetrievedData(BaseModel):
    """Data retrieved from an Excel file for answering a query."""
    file_name: str = Field(..., description="File name")
    file_path: str = Field(..., description="Full file path")
    sheet_name: str = Field(..., description="Sheet name")
    cell_range: str = Field(..., description="Cell range (e.g., 'A1:B10')")
    data: Any = Field(..., description="The actual data")
    data_type: DataType = Field(..., description="Type of data")
    original_format: Optional[str] = Field(default=None, description="Original Excel format")

    class Config:
        json_schema_extra = {
            "example": {
                "file_name": "Expenses_Jan2024.xlsx",
                "file_path": "/Finance/2024/Expenses_Jan2024.xlsx",
                "sheet_name": "Summary",
                "cell_range": "B10",
                "data": 1500.50,
                "data_type": "number",
                "original_format": "$#,##0.00"
            }
        }


class AlignedData(BaseModel):
    """Data aligned across multiple files for comparison."""
    common_columns: List[str] = Field(default_factory=list, description="Columns present in all files")
    file_data: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Data from each file, keyed by file_id"
    )
    missing_columns: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Columns missing from each file, keyed by file_id"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "common_columns": ["Month", "Revenue", "Expenses"],
                "file_data": {
                    "file1": [{"Month": "Jan", "Revenue": 10000, "Expenses": 7000}],
                    "file2": [{"Month": "Jan", "Revenue": 12000, "Expenses": 8000}]
                },
                "missing_columns": {
                    "file1": ["Profit"],
                    "file2": []
                }
            }
        }


class ComparisonResult(BaseModel):
    """Result of comparing data across multiple files."""
    files_compared: List[str] = Field(..., description="List of file names compared")
    aligned_data: Dict[str, Any] = Field(..., description="Aligned data structure")
    differences: Dict[str, Any] = Field(..., description="Calculated differences")
    summary: str = Field(..., description="Natural language summary of comparison")
    visualization_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Data formatted for visualization"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "files_compared": ["Expenses_Jan2024.xlsx", "Expenses_Feb2024.xlsx"],
                "aligned_data": {},
                "differences": {
                    "Revenue": {"absolute": 2000, "percentage": 20.0, "trend": "increasing"}
                },
                "summary": "Revenue increased by $2,000 (20%) from January to February",
                "visualization_data": None
            }
        }


class QueryResult(BaseModel):
    """Result of processing a user query."""
    answer: str = Field(..., description="Natural language answer")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    sources: List[RetrievedData] = Field(default_factory=list, description="Data sources used")
    clarification_needed: bool = Field(default=False, description="Whether clarification is needed")
    clarifying_questions: List[str] = Field(default_factory=list, description="Questions to ask user")
    processing_time_ms: int = Field(..., ge=0, description="Processing time in milliseconds")
    is_comparison: bool = Field(default=False, description="Whether this is a comparison query")
    comparison_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Summary for comparison queries"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "The total expenses for January 2024 were $7,000.",
                "confidence": 0.95,
                "sources": [],
                "clarification_needed": False,
                "clarifying_questions": [],
                "processing_time_ms": 1250,
                "is_comparison": False,
                "comparison_summary": None
            }
        }


class ConversationContext(BaseModel):
    """Context for maintaining conversation state."""
    previous_queries: List[str] = Field(default_factory=list, description="Previous queries in session")
    selected_files: List[str] = Field(default_factory=list, description="Files selected in session")
    session_id: str = Field(..., description="Unique session identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "previous_queries": ["What were the expenses in January?"],
                "selected_files": ["1abc123def456"],
                "session_id": "sess_abc123"
            }
        }


class IndexingReport(BaseModel):
    """Report of indexing operation results."""
    total_files: int = Field(..., ge=0, description="Total files discovered")
    total_sheets: int = Field(..., ge=0, description="Total sheets processed")
    files_processed: int = Field(..., ge=0, description="Files successfully processed")
    files_failed: int = Field(..., ge=0, description="Files that failed processing")
    files_skipped: int = Field(default=0, ge=0, description="Files skipped (unchanged)")
    duration_seconds: float = Field(..., ge=0.0, description="Total duration in seconds")
    errors: List[str] = Field(default_factory=list, description="Error messages")

    class Config:
        json_schema_extra = {
            "example": {
                "total_files": 50,
                "total_sheets": 125,
                "files_processed": 48,
                "files_failed": 2,
                "files_skipped": 0,
                "duration_seconds": 180.5,
                "errors": ["Failed to process corrupted_file.xlsx: Invalid file format"]
            }
        }
