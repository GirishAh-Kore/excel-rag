"""
Unstructured.io Excel Extractor

Document chunking and extraction optimized for RAG pipelines.
Can run locally or via hosted API.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.models.domain_models import SheetData, WorkbookData, DataType

logger = logging.getLogger(__name__)


class UnstructuredExcelExtractor:
    """
    Excel extractor using Unstructured.io (open-source).
    
    Unstructured provides:
    - Intelligent document partitioning
    - Table extraction with structure preservation
    - Chunking optimized for RAG
    - Runs 100% locally (no API key needed)
    - Optional: hosted API for serverless deployment
    """
    
    def __init__(self, config=None):
        """
        Initialize Unstructured extractor.
        
        By default runs locally. API key/URL only needed for hosted service.
        
        Args:
            config: ExtractionConfig with unstructured settings
        """
        self.config = config
        # API settings are optional - local mode is the default
        self.api_key = getattr(config, 'unstructured_api_key', None) if config else None
        self.api_url = getattr(config, 'unstructured_api_url', None) if config else None
        self.strategy = getattr(config, 'unstructured_strategy', 'auto') if config else 'auto'
        self._initialized = False
        
    def _ensure_initialized(self):
        """Verify unstructured is available."""
        if self._initialized:
            return
            
        try:
            from unstructured.partition.xlsx import partition_xlsx
            from unstructured.partition.auto import partition
            self._initialized = True
            logger.info("Unstructured.io extractor initialized")
            
        except ImportError as e:
            logger.error(
                "unstructured not installed. Install with: "
                "pip install 'unstructured[xlsx]'"
            )
            raise ImportError(
                "unstructured package required. Install: pip install 'unstructured[xlsx]'"
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
        Extract workbook using Unstructured.io.
        
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
        
        # Write to temp file
        suffix = '.xlsx' if file_name.lower().endswith('.xlsx') else '.xls'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            # Use API or local processing
            if self.api_key and self.api_url:
                elements = await self._partition_via_api(tmp_path)
            else:
                elements = self._partition_local(tmp_path)
            
            # Convert elements to sheets
            sheets = self._elements_to_sheets(elements, file_name)
            
            return WorkbookData(
                file_id=file_id,
                file_name=file_name,
                file_path=file_path,
                modified_time=modified_time,
                sheets=sheets,
                total_sheets=len(sheets),
                file_size_bytes=len(file_content),
                extraction_method="unstructured"
            )
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def _partition_local(self, file_path: str) -> List:
        """
        Partition document locally using unstructured.
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            List of unstructured Elements
        """
        from unstructured.partition.xlsx import partition_xlsx
        
        elements = partition_xlsx(
            filename=file_path,
            infer_table_structure=True,
            include_page_breaks=True
        )
        
        logger.info(f"Extracted {len(elements)} elements from Excel")
        return elements
    
    async def _partition_via_api(self, file_path: str) -> List:
        """
        Partition document via Unstructured API.
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            List of unstructured Elements
        """
        from unstructured_client import UnstructuredClient
        from unstructured_client.models import shared
        
        client = UnstructuredClient(
            api_key_auth=self.api_key,
            server_url=self.api_url
        )
        
        with open(file_path, "rb") as f:
            files = shared.Files(
                content=f.read(),
                file_name=file_path.split("/")[-1]
            )
        
        req = shared.PartitionParameters(
            files=files,
            strategy=self.strategy,
            xlsx_infer_table_structure=True
        )
        
        resp = client.general.partition(req)
        
        logger.info(f"API extracted {len(resp.elements)} elements")
        return resp.elements
    
    def _elements_to_sheets(self, elements: List, file_name: str) -> List[SheetData]:
        """
        Convert Unstructured elements to SheetData objects.
        
        Groups elements by page/sheet and extracts tables.
        
        Args:
            elements: List of Unstructured Elements
            file_name: Source file name
            
        Returns:
            List of SheetData objects
        """
        from unstructured.documents.elements import Table, Title, NarrativeText
        
        sheets = []
        current_sheet_name = "Sheet1"
        current_elements = []
        sheet_idx = 1
        
        for element in elements:
            # Check for sheet/page breaks
            metadata = getattr(element, 'metadata', None)
            if metadata:
                page_name = getattr(metadata, 'page_name', None)
                if page_name and page_name != current_sheet_name:
                    # Save current sheet
                    if current_elements:
                        sheets.append(self._create_sheet(
                            current_sheet_name, current_elements, file_name
                        ))
                    current_sheet_name = page_name
                    current_elements = []
                    sheet_idx += 1
            
            current_elements.append(element)
        
        # Save last sheet
        if current_elements:
            sheets.append(self._create_sheet(
                current_sheet_name, current_elements, file_name
            ))
        
        # If no sheets created, create one from all elements
        if not sheets and elements:
            sheets.append(self._create_sheet("Sheet1", elements, file_name))
        
        return sheets
    
    def _create_sheet(
        self,
        sheet_name: str,
        elements: List,
        file_name: str
    ) -> SheetData:
        """
        Create SheetData from Unstructured elements.
        
        Args:
            sheet_name: Name for the sheet
            elements: List of elements for this sheet
            file_name: Source file name
            
        Returns:
            SheetData object
        """
        from unstructured.documents.elements import Table
        
        headers = []
        rows = []
        data_types = {}
        
        # Find tables in elements
        tables = [e for e in elements if isinstance(e, Table)]
        
        if tables:
            # Use first table for structure
            table = tables[0]
            headers, rows, data_types = self._parse_table_element(table)
        else:
            # Create text-based sheet
            text_content = "\n".join(str(e) for e in elements)
            headers = ["content"]
            rows = [{"content": text_content}]
            data_types = {"content": DataType.TEXT}
        
        return SheetData(
            sheet_name=sheet_name,
            headers=headers,
            rows=rows,
            row_count=len(rows),
            column_count=len(headers),
            data_types=data_types,
            has_dates=any(dt == DataType.DATE for dt in data_types.values()),
            has_numbers=any(dt == DataType.NUMBER for dt in data_types.values()),
            summary=f"Sheet '{sheet_name}' from {file_name} via Unstructured",
            pivot_tables=[],
            charts=[],
            has_pivot_tables=False,
            has_charts=False
        )
    
    def _parse_table_element(self, table) -> tuple:
        """
        Parse an Unstructured Table element.
        
        Args:
            table: Unstructured Table element
            
        Returns:
            Tuple of (headers, rows, data_types)
        """
        headers = []
        rows = []
        data_types = {}
        
        try:
            # Get table HTML and parse
            html = table.metadata.text_as_html if hasattr(table.metadata, 'text_as_html') else None
            
            if html:
                import pandas as pd
                dfs = pd.read_html(html)
                if dfs:
                    df = dfs[0]
                    headers = [str(c) for c in df.columns]
                    rows = df.to_dict('records')
                    
                    # Infer types
                    for col in headers:
                        if df[col].dtype in ['int64', 'float64']:
                            data_types[col] = DataType.NUMBER
                        elif 'datetime' in str(df[col].dtype):
                            data_types[col] = DataType.DATE
                        else:
                            data_types[col] = DataType.TEXT
            else:
                # Fallback to text
                headers = ["value"]
                rows = [{"value": str(table)}]
                data_types = {"value": DataType.TEXT}
                
        except Exception as e:
            logger.warning(f"Error parsing table: {e}")
            headers = ["value"]
            rows = [{"value": str(table)}]
            data_types = {"value": DataType.TEXT}
        
        return headers, rows, data_types
    
    def get_chunks(
        self,
        elements: List,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get RAG-optimized chunks from elements.
        
        Unstructured's main strength is intelligent chunking.
        
        Args:
            elements: List of Unstructured elements
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        from unstructured.chunking.title import chunk_by_title
        
        chunks = chunk_by_title(
            elements,
            max_characters=chunk_size,
            overlap=overlap,
            combine_text_under_n_chars=100
        )
        
        return [
            {
                "text": str(chunk),
                "metadata": {
                    "element_type": type(chunk).__name__,
                    "page": getattr(chunk.metadata, 'page_number', None),
                }
            }
            for chunk in chunks
        ]
