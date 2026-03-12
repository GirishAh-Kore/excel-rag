"""
IBM Docling Excel Extractor

Open-source document understanding using IBM's Docling library.
Provides structured extraction with table detection and layout analysis.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.models.domain_models import SheetData, WorkbookData, DataType

logger = logging.getLogger(__name__)


class DoclingExcelExtractor:
    """
    Excel extractor using IBM Docling (open-source).
    
    Docling provides:
    - Advanced table detection
    - Layout analysis
    - Structured document understanding
    - No API costs (runs locally)
    """
    
    def __init__(self, config=None):
        """
        Initialize Docling extractor.
        
        Args:
            config: ExtractionConfig with docling settings
        """
        self.config = config
        self._converter = None
        self._initialized = False
        
    def _ensure_initialized(self):
        """Lazy initialization of Docling."""
        if self._initialized:
            return
            
        try:
            from docling.document_converter import DocumentConverter
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            
            # Configure for Excel/spreadsheet processing
            self._converter = DocumentConverter()
            self._initialized = True
            logger.info("Docling extractor initialized successfully")
            
        except ImportError as e:
            logger.error(
                "Docling not installed. Install with: pip install docling"
            )
            raise ImportError(
                "docling package required. Install: pip install docling"
            ) from e
    
    async def extract_workbook(
        self,
        file_content: bytes,
        file_id: str,
        file_name: str,
        file_path: str,
        modified_time: datetime
    ) -> WorkbookData:
        """
        Extract workbook using Docling.
        
        Args:
            file_content: Raw bytes of Excel file
            file_id: File identifier
            file_name: File name
            file_path: Full path
            modified_time: Last modified timestamp
            
        Returns:
            WorkbookData with extracted information
        """
        self._ensure_initialized()
        
        import tempfile
        import os
        
        # Write to temp file (Docling needs file path)
        with tempfile.NamedTemporaryFile(
            suffix=self._get_suffix(file_name),
            delete=False
        ) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            # Convert document
            result = self._converter.convert(tmp_path)
            
            # Extract sheets from Docling result
            sheets = self._parse_docling_result(result, file_name)
            
            return WorkbookData(
                file_id=file_id,
                file_name=file_name,
                file_path=file_path,
                modified_time=modified_time,
                sheets=sheets,
                total_sheets=len(sheets),
                file_size_bytes=len(file_content),
                extraction_method="docling"
            )
            
        finally:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def _get_suffix(self, file_name: str) -> str:
        """Get file suffix from name."""
        if file_name.lower().endswith('.xlsx'):
            return '.xlsx'
        elif file_name.lower().endswith('.xls'):
            return '.xls'
        return '.xlsx'
    
    def _parse_docling_result(self, result, file_name: str) -> List[SheetData]:
        """
        Parse Docling conversion result into SheetData objects.
        
        Args:
            result: Docling ConversionResult
            file_name: Source file name
            
        Returns:
            List of SheetData objects
        """
        sheets = []
        
        # Docling returns document with tables
        doc = result.document
        
        # Extract tables as sheets
        for idx, table in enumerate(doc.tables):
            sheet_name = f"Table_{idx + 1}"
            
            # Parse table data
            headers, rows, data_types = self._parse_table(table)
            
            sheets.append(SheetData(
                sheet_name=sheet_name,
                headers=headers,
                rows=rows,
                row_count=len(rows),
                column_count=len(headers),
                data_types=data_types,
                has_dates=any(dt == DataType.DATE for dt in data_types.values()),
                has_numbers=any(dt == DataType.NUMBER for dt in data_types.values()),
                summary=f"Table extracted from {file_name} using Docling",
                pivot_tables=[],
                charts=[],
                has_pivot_tables=False,
                has_charts=False
            ))
        
        # If no tables found, create a single sheet from text content
        if not sheets:
            text_content = doc.export_to_markdown()
            sheets.append(SheetData(
                sheet_name="Content",
                headers=["content"],
                rows=[{"content": text_content}],
                row_count=1,
                column_count=1,
                data_types={"content": DataType.TEXT},
                has_dates=False,
                has_numbers=False,
                summary=f"Content extracted from {file_name}",
                pivot_tables=[],
                charts=[],
                has_pivot_tables=False,
                has_charts=False
            ))
        
        return sheets
    
    def _parse_table(self, table) -> tuple:
        """
        Parse a Docling table into headers, rows, and data types.
        
        Args:
            table: Docling TableItem
            
        Returns:
            Tuple of (headers, rows, data_types)
        """
        headers = []
        rows = []
        data_types = {}
        
        try:
            # Get table grid
            grid = table.export_to_dataframe()
            
            # Extract headers from first row or column names
            headers = list(grid.columns)
            
            # Convert rows to list of dicts
            for _, row in grid.iterrows():
                rows.append(dict(row))
            
            # Infer data types
            for col in headers:
                sample_values = [r.get(col) for r in rows[:10] if r.get(col)]
                data_types[col] = self._infer_data_type(sample_values)
                
        except Exception as e:
            logger.warning(f"Error parsing Docling table: {e}")
            headers = ["value"]
            rows = [{"value": str(table)}]
            data_types = {"value": DataType.TEXT}
        
        return headers, rows, data_types
    
    def _infer_data_type(self, values: List[Any]) -> DataType:
        """Infer data type from sample values."""
        if not values:
            return DataType.TEXT
            
        # Check for numbers
        numeric_count = 0
        for v in values:
            try:
                float(str(v).replace(',', ''))
                numeric_count += 1
            except (ValueError, TypeError):
                pass
        
        if numeric_count > len(values) * 0.7:
            return DataType.NUMBER
        
        # Check for dates
        from dateutil import parser as date_parser
        date_count = 0
        for v in values:
            try:
                date_parser.parse(str(v))
                date_count += 1
            except:
                pass
        
        if date_count > len(values) * 0.7:
            return DataType.DATE
        
        return DataType.TEXT
