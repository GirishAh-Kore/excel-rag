# Content Extraction Module

This module provides comprehensive Excel file extraction capabilities for the Google Drive Excel RAG system.

## Features

- **Multi-format Support**: Handles .xlsx files via openpyxl (legacy .xls support via xlrd)
- **Comprehensive Data Extraction**:
  - Cell values with data type preservation
  - Formulas (both text and calculated values)
  - Cell formatting (currency, percentage, dates)
  - Merged cells
  - Pivot tables
  - Charts
- **Smart Header Detection**: Automatically identifies header rows
- **Embedding Text Generation**: Creates multiple text chunks optimized for semantic search
- **Robust Error Handling**: Gracefully handles corrupted files, unsupported formats, and memory issues

## Usage

### Basic Extraction

```python
from src.extraction import ContentExtractor
from datetime import datetime

# Initialize extractor
extractor = ContentExtractor(max_rows_per_sheet=10000)

# Extract workbook
with open("file.xlsx", "rb") as f:
    file_content = f.read()

workbook_data = extractor.extract_workbook(
    file_content=file_content,
    file_id="file_123",
    file_name="expenses.xlsx",
    file_path="/Finance/expenses.xlsx",
    modified_time=datetime.now()
)

# Access extracted data
for sheet in workbook_data.sheets:
    print(f"Sheet: {sheet.sheet_name}")
    print(f"Headers: {sheet.headers}")
    print(f"Rows: {sheet.row_count}")
    print(f"Has pivot tables: {sheet.has_pivot_tables}")
    print(f"Has charts: {sheet.has_charts}")
```

### Generate Embedding Text

```python
# Generate text chunks for embedding
for sheet in workbook_data.sheets:
    chunks = extractor.generate_embeddings_text(sheet, workbook_data.file_name)
    for chunk in chunks:
        print(chunk)
```

### Error Handling

```python
from src.extraction import (
    ContentExtractor,
    CorruptedFileError,
    UnsupportedFormatError,
    MemoryError
)

extractor = ContentExtractor()

try:
    workbook_data = extractor.extract_workbook(...)
except CorruptedFileError as e:
    print(f"File is corrupted: {e}")
except UnsupportedFormatError as e:
    print(f"Unsupported format: {e}")
except MemoryError as e:
    print(f"File too large: {e}")

# Get list of failed files
failed_files = extractor.get_failed_files()
for failed in failed_files:
    print(f"Failed: {failed['file_name']} - {failed['error_type']}")
```

### Cell Formatting

```python
# Extract cell with formatting
cell = worksheet['A1']
cell_data = extractor._extract_cell_data(cell, worksheet)

print(f"Value: {cell_data.value}")
print(f"Format: {cell_data.format}")
print(f"Is formula: {cell_data.is_formula}")
print(f"Formula: {cell_data.formula}")

# Format cell value
formatted = extractor.format_cell_value(cell_data)
print(f"Formatted: {formatted}")
```

## Data Models

The extractor returns structured data using Pydantic models:

- **WorkbookData**: Complete workbook with all sheets
- **SheetData**: Single sheet with headers, rows, and metadata
- **CellData**: Individual cell with value, type, formula, and format
- **PivotTableData**: Pivot table definition and metadata
- **ChartData**: Chart metadata and source data references

## Configuration

```python
# Configure maximum rows per sheet
extractor = ContentExtractor(max_rows_per_sheet=10000)

# File size limit: 100 MB (hardcoded for memory protection)
```

## Error Types

- **ExtractionError**: Base exception for all extraction errors
- **CorruptedFileError**: File is corrupted or invalid
- **UnsupportedFormatError**: File format not supported (e.g., password-protected)
- **MemoryError**: File too large to process (> 100 MB)

## Limitations

- Legacy .xls files have limited support (warning logged)
- Pivot table calculated results not extracted (only definitions)
- Chart images not extracted (only metadata)
- Maximum file size: 100 MB
- Maximum rows per sheet: 10,000 (configurable)

## Testing

Run tests with:

```bash
pytest tests/test_content_extractor.py -v
```

## Requirements

- openpyxl >= 3.1.2
- xlrd >= 2.0.1 (for legacy .xls support)
- python-dateutil >= 2.8.2
