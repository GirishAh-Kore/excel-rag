# Comparison Engine

The Comparison Engine enables comparing data across multiple Excel files, handling alignment, difference calculation, and result formatting.

## Overview

The comparison engine consists of four main components:

1. **ComparisonEngine**: Orchestrates the entire comparison workflow
2. **SheetAligner**: Aligns sheets from different files using fuzzy matching
3. **DifferenceCalculator**: Calculates differences, trends, and aggregates
4. **ComparisonFormatter**: Formats results with natural language summaries

## Architecture

```
ComparisonEngine
├── SheetAligner (aligns sheets and columns)
├── DifferenceCalculator (computes differences)
└── ComparisonFormatter (generates summaries)
```

## Components

### ComparisonEngine

The main orchestrator that coordinates the comparison workflow.

**Key Methods:**
- `compare_files(file_ids, query, sheet_names)`: Compare multiple files
- `_retrieve_sheets()`: Download and extract sheets from files
- `_align_sheets()`: Align sheets using SheetAligner
- `_calculate_differences()`: Calculate differences using DifferenceCalculator
- `_format_results()`: Format results using ComparisonFormatter

**Features:**
- Handles up to 5 files per comparison
- Supports specific sheet selection
- Graceful error handling for missing files
- Parallel sheet retrieval

### SheetAligner

Aligns sheets from different files for comparison.

**Key Methods:**
- `align_sheets(sheets, file_ids)`: Align multiple sheets
- `_group_sheets_by_name()`: Group similar sheets using fuzzy matching
- `_find_common_columns()`: Identify columns present in all sheets
- `_align_rows()`: Align rows based on key columns

**Features:**
- Fuzzy sheet name matching (Levenshtein distance < 3, threshold 0.8)
- Fuzzy column name matching (threshold 0.85)
- Automatic key column detection (dates, IDs, categories)
- Missing column tracking
- Row sorting by key columns

**Configuration:**
```python
aligner = SheetAligner(
    sheet_name_threshold=0.8,      # Fuzzy matching threshold for sheet names
    column_name_threshold=0.85,    # Fuzzy matching threshold for columns
    max_levenshtein_distance=3     # Maximum edit distance for matching
)
```

### DifferenceCalculator

Calculates differences and trends across aligned data.

**Key Methods:**
- `calculate_differences(aligned_data)`: Calculate all differences
- `_calculate_column_differences()`: Per-column difference calculation
- `_calculate_aggregates()`: Compute sum, average, min, max, count
- `_detect_trends()`: Identify increasing/decreasing/stable trends

**Features:**
- Absolute differences (value2 - value1)
- Percentage changes with division-by-zero handling
- Trend detection (±5% threshold for stable)
- Aggregate statistics across all files
- Missing data handling

**Configuration:**
```python
calculator = DifferenceCalculator(
    stable_threshold=0.05,           # ±5% for stable trend
    min_value_for_percentage=0.01    # Minimum value for percentage calc
)
```

**Output Structure:**
```python
{
    "column_differences": {
        "Revenue": {
            "file1_vs_file2": {
                "absolute_difference": 2000,
                "percentage_change": 20.0,
                "trend": "increasing",
                "value1_avg": 10000,
                "value2_avg": 12000,
                "missing_data": False
            }
        }
    },
    "aggregates": {
        "Revenue": {
            "sum": 22000,
            "average": 11000,
            "min": 10000,
            "max": 12000,
            "count": 2
        }
    },
    "trends": {
        "Revenue": "increasing",
        "Expenses": "stable"
    },
    "summary_stats": {
        "total_files": 2,
        "total_columns": 3,
        "total_rows": 4,
        "files_with_missing_columns": 0
    }
}
```

### ComparisonFormatter

Formats comparison results for presentation.

**Key Methods:**
- `format_comparison()`: Create formatted ComparisonResult
- `_generate_summary()`: Generate natural language summary
- `_create_visualization_data()`: Create data for charts/tables
- `_cache_aligned_data()`: Cache results for follow-up questions

**Features:**
- LLM-generated summaries (with template fallback)
- Structured visualization data
- Source citations for all values
- 5-minute cache for follow-up questions
- Comparison tables with aligned data

**Configuration:**
```python
formatter = ComparisonFormatter(
    llm_service=llm_service,      # Optional LLM for summaries
    cache_service=cache_service,  # Optional cache for aligned data
    cache_ttl=300                 # Cache TTL in seconds (5 minutes)
)
```

## Usage Examples

### Basic Comparison

```python
from src.query.comparison_engine import ComparisonEngine
from src.gdrive.connector import GoogleDriveConnector
from src.extraction.content_extractor import ContentExtractor

# Initialize
gdrive_connector = GoogleDriveConnector(...)
content_extractor = ContentExtractor()
comparison_engine = ComparisonEngine(
    gdrive_connector=gdrive_connector,
    content_extractor=content_extractor
)

# Compare files
result = comparison_engine.compare_files(
    file_ids=["file1_id", "file2_id"],
    query="Compare expenses between January and February"
)

print(result.summary)
print(result.differences)
```

### Sheet Alignment

```python
from src.query.sheet_aligner import SheetAligner
from src.models.domain_models import SheetData

# Create aligner
aligner = SheetAligner()

# Align sheets
aligned_data = aligner.align_sheets(
    sheets=[sheet1, sheet2, sheet3],
    file_ids=["file1", "file2", "file3"]
)

print(f"Common columns: {aligned_data.common_columns}")
print(f"Missing columns: {aligned_data.missing_columns}")
```

### Difference Calculation

```python
from src.query.difference_calculator import DifferenceCalculator
from src.models.domain_models import AlignedData

# Create calculator
calculator = DifferenceCalculator()

# Calculate differences
differences = calculator.calculate_differences(aligned_data)

# Access results
for column, diffs in differences["column_differences"].items():
    print(f"{column}: {diffs}")

print(f"Trends: {differences['trends']}")
print(f"Aggregates: {differences['aggregates']}")
```

### Comparison Formatting

```python
from src.query.comparison_formatter import ComparisonFormatter
from src.abstractions.llm_service_factory import LLMServiceFactory

# Create formatter with LLM
llm_service = LLMServiceFactory.create("openai", {...})
formatter = ComparisonFormatter(llm_service=llm_service)

# Format results
result = formatter.format_comparison(
    file_ids=["file1", "file2"],
    aligned_data=aligned_data,
    differences=differences,
    query="Compare revenue"
)

print(result.summary)  # Natural language summary
print(result.visualization_data)  # Data for charts
```

## Comparison Types Supported

### 1. Temporal Comparisons
Compare data across time periods:
- "Compare expenses between January and February"
- "How did revenue change from Q1 to Q2?"
- "Show me the trend in sales over the last 3 months"

### 2. Categorical Comparisons
Compare data across categories:
- "Compare sales across regions"
- "Which department had higher expenses?"
- "Show differences between product categories"

### 3. Structural Comparisons
Identify structural differences:
- "Which files have travel expenses?"
- "Compare the structure of these reports"
- "What columns are missing in file2?"

## Alignment Strategy

### Sheet Matching
1. Group sheets by similar names using fuzzy matching
2. Levenshtein distance < 3 or similarity > 80%
3. Case-insensitive comparison

### Column Matching
1. Find columns present in all sheets
2. Use fuzzy matching (threshold 85%)
3. Track missing columns per file

### Row Alignment
1. Identify key columns (dates, IDs, categories)
2. Sort rows by key columns
3. Handle different row counts gracefully

## Performance Considerations

- **File Limit**: Maximum 5 files per comparison
- **Row Limit**: First 10,000 rows per sheet
- **Caching**: Aligned data cached for 5 minutes
- **Parallel Processing**: Files retrieved in parallel

## Error Handling

### Missing Files
- Logs error and continues with available files
- Returns partial results if some files succeed

### Structural Differences
- Tracks missing columns per file
- Logs warnings for row count differences
- Includes alignment quality score

### Division by Zero
- Returns None for percentage when base value < 0.01
- Handles zero values gracefully in calculations

### Missing Data
- Marks missing data points in results
- Continues calculation with available data
- Reports data completeness in summary

## Integration with Query Engine

The ComparisonEngine integrates with the QueryEngine for comparison queries:

```python
# In QueryEngine
if query_analysis.is_comparison:
    # Use SemanticSearcher to find multiple files
    search_results = semantic_searcher.search(
        query=query,
        top_k=5,  # Get up to 5 files
        comparison_mode=True
    )
    
    # Extract file IDs
    file_ids = [result.file_id for result in search_results]
    
    # Use ComparisonEngine
    comparison_result = comparison_engine.compare_files(
        file_ids=file_ids,
        query=query
    )
    
    # Return comparison result
    return QueryResult(
        answer=comparison_result.summary,
        is_comparison=True,
        comparison_summary=comparison_result.differences,
        sources=[...]
    )
```

## Testing

See `examples/comparison_usage.py` for comprehensive usage examples.

### Unit Tests
- Test sheet alignment with various structures
- Test difference calculation with edge cases
- Test formatting with and without LLM
- Test error handling

### Integration Tests
- Test end-to-end comparison workflow
- Test with real Excel files
- Test caching behavior
- Test multi-file scenarios

## Future Enhancements

1. **Advanced Alignment**: Support for complex key column combinations
2. **Statistical Analysis**: Correlation, regression, significance tests
3. **Visualization**: Generate charts directly from comparison data
4. **Export**: Export comparison results to Excel/PDF
5. **Incremental Comparison**: Compare only changed rows
6. **Custom Metrics**: User-defined comparison metrics
7. **Temporal Analysis**: Automatic time-series trend detection

## Dependencies

- `python-Levenshtein`: Fuzzy string matching
- `src.models.domain_models`: Data models
- `src.gdrive.connector`: Google Drive access
- `src.extraction.content_extractor`: Excel parsing
- `src.abstractions.llm_service`: LLM for summaries
- `src.abstractions.cache_service`: Caching aligned data

## Configuration

Environment variables for comparison engine:

```bash
# LLM for summary generation (optional)
LLM_PROVIDER=openai
LLM_API_KEY=your_api_key
LLM_MODEL=gpt-4

# Cache for aligned data (optional)
CACHE_PROVIDER=redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Comparison settings
COMPARISON_MAX_FILES=5
COMPARISON_CACHE_TTL=300
COMPARISON_STABLE_THRESHOLD=0.05
```

## Troubleshooting

### Issue: Sheets not aligning properly
**Solution**: Adjust fuzzy matching thresholds:
```python
aligner = SheetAligner(
    sheet_name_threshold=0.7,  # Lower threshold
    column_name_threshold=0.8
)
```

### Issue: Too many missing columns
**Solution**: Check column name consistency across files. Use exact column names when possible.

### Issue: Incorrect trends detected
**Solution**: Adjust stable threshold:
```python
calculator = DifferenceCalculator(
    stable_threshold=0.10  # ±10% for stable
)
```

### Issue: LLM summary generation fails
**Solution**: Formatter falls back to template-based summary automatically. Check LLM service configuration if needed.

## See Also

- [Query Engine README](README.md)
- [File Selector](file_selector.py)
- [Sheet Selector](sheet_selector.py)
- [Design Document](../../.kiro/specs/gdrive-excel-rag/design.md)
