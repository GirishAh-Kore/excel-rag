# Extraction Enhancements: LLM Summarization & Configurable Strategies

## Overview

This document describes the enhancements made to the Excel extraction system to support:
1. **LLM-based sheet summarization** for improved disambiguation
2. **Configurable extraction strategies** with multiple backends
3. **Smart fallback mechanisms** for handling complex files

## Features Implemented

### 1. LLM Sheet Summarization

**Purpose**: Generate semantic summaries of Excel sheets to improve sheet selection when multiple candidates match a query.

**Key Components**:
- `SheetSummarizer` class for generating LLM-based summaries
- Integration with existing LLM service abstractions
- Automatic summary generation during indexing
- Sheet ranking based on query relevance

**Benefits**:
- Better understanding of sheet purpose beyond just headers
- Improved accuracy in sheet selection (disambiguation)
- Natural language descriptions for user-facing interfaces
- Semantic ranking of sheets for ambiguous queries

**Usage**:
```python
from src.extraction import SheetSummarizer, ExtractionConfig

config = ExtractionConfig(
    enable_llm_summarization=True,
    summarization_provider="openai",
    summarization_model="gpt-4o-mini"
)

summarizer = SheetSummarizer(config)

# Generate summary for a sheet
summary = await summarizer.generate_sheet_summary(
    sheet_data=sheet,
    file_name="expenses.xlsx"
)

# Rank sheets for a query
ranked = await summarizer.rank_sheets_for_query(
    query="What were the expenses?",
    candidate_sheets=[(sheet1, "file1.xlsx"), (sheet2, "file1.xlsx")]
)
```

### 2. Configurable Extraction Strategies

**Purpose**: Support multiple extraction backends with automatic fallback for complex files.

**Supported Strategies**:
1. **openpyxl** (default): Fast, free, local processing
2. **Gemini** (optional): Google's multimodal understanding
3. **LlamaParse** (optional): Document understanding
4. **AUTO**: Automatically choose best strategy

**Key Components**:
- `ExtractionStrategy` enum for strategy selection
- `ExtractionConfig` for configuration
- `ConfigurableExtractor` for unified interface
- Quality evaluation for smart fallback

**Architecture**:
```
ConfigurableExtractor
├── ContentExtractor (openpyxl) - Default, always available
├── GeminiExcelExtractor - Optional, requires API key
├── LlamaParseExtractor - Optional, requires API key
└── SheetSummarizer - Optional, for LLM summaries
```

**Usage**:
```python
from src.extraction import ConfigurableExtractor, ExtractionConfig, ExtractionStrategy

# Configure extraction
config = ExtractionConfig(
    default_strategy=ExtractionStrategy.OPENPYXL,
    enable_llm_summarization=True,
    enable_gemini=True,
    gemini_fallback_on_error=True,
    use_auto_strategy=True
)

extractor = ConfigurableExtractor(config)

# Extract with automatic strategy selection
workbook = await extractor.extract_workbook(
    file_content=file_bytes,
    file_id="123",
    file_name="data.xlsx",
    file_path="/data.xlsx",
    modified_time=datetime.now()
)
```

### 3. Smart Extraction with Quality Evaluation

**Purpose**: Automatically choose the best extraction strategy based on quality metrics.

**Quality Metrics**:
- Has headers detected
- Has data rows extracted
- Data completeness (% non-empty cells)
- Structure clarity (column count normalization)
- Extraction errors count

**Fallback Logic**:
1. Try openpyxl first (fast and free)
2. Evaluate extraction quality
3. If quality < threshold and Gemini enabled → use Gemini
4. If openpyxl fails and Gemini enabled → use Gemini

**Configuration**:
```python
config = ExtractionConfig(
    use_auto_strategy=True,
    complexity_threshold=0.7,  # Quality threshold for fallback
    gemini_fallback_on_error=True
)
```

## Configuration

### Environment Variables

```bash
# Extraction Strategy
EXTRACTION_STRATEGY=openpyxl  # openpyxl, gemini, llamaparse, auto
MAX_ROWS_PER_SHEET=10000
MAX_FILE_SIZE_MB=100

# LLM Summarization
ENABLE_LLM_SUMMARIZATION=true
SUMMARIZATION_PROVIDER=openai  # openai, anthropic, gemini
SUMMARIZATION_MODEL=gpt-4o-mini  # Optional, uses provider default
SUMMARIZATION_MAX_TOKENS=150

# Google Gemini (Optional)
ENABLE_GEMINI_EXTRACTION=false
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash
GEMINI_FALLBACK_ON_ERROR=true

# LlamaParse (Optional)
ENABLE_LLAMAPARSE=false
LLAMAPARSE_API_KEY=your_llamaparse_api_key

# Smart Extraction
USE_AUTO_EXTRACTION_STRATEGY=false
EXTRACTION_COMPLEXITY_THRESHOLD=0.7
```

### Python Configuration

```python
from src.extraction import ExtractionConfig, ExtractionStrategy

config = ExtractionConfig(
    # Primary settings
    default_strategy=ExtractionStrategy.OPENPYXL,
    max_rows_per_sheet=10000,
    max_file_size_mb=100,
    
    # LLM Summarization
    enable_llm_summarization=True,
    summarization_provider="openai",
    summarization_model="gpt-4o-mini",
    summarization_max_tokens=150,
    
    # Gemini
    enable_gemini=False,
    gemini_api_key=None,
    gemini_model="gemini-1.5-flash",
    gemini_fallback_on_error=True,
    
    # LlamaParse
    enable_llamaparse=False,
    llamaparse_api_key=None,
    
    # Smart extraction
    use_auto_strategy=False,
    complexity_threshold=0.7
)
```

## Data Model Changes

### SheetData Model

Added two new fields to support LLM summarization:

```python
class SheetData(BaseModel):
    # ... existing fields ...
    llm_summary: Optional[str] = None  # LLM-generated semantic summary
    summary_generated_at: Optional[datetime] = None  # Timestamp
```

## Use Cases

### Use Case 1: Basic Extraction with LLM Summaries

```python
config = ExtractionConfig(
    enable_llm_summarization=True,
    summarization_provider="openai"
)

extractor = ConfigurableExtractor(config)
workbook = await extractor.extract_workbook(...)

# Access LLM summaries
for sheet in workbook.sheets:
    print(f"Sheet: {sheet.sheet_name}")
    print(f"Summary: {sheet.llm_summary}")
```

### Use Case 2: Disambiguation with Multiple Sheets

```python
# User query matches multiple sheets
query = "What were the expenses?"

# Rank sheets by relevance
ranked = await summarizer.rank_sheets_for_query(
    query=query,
    candidate_sheets=[(sheet1, "file.xlsx"), (sheet2, "file.xlsx")]
)

# Present top results to user
for sheet, score, summary in ranked[:3]:
    print(f"{sheet.sheet_name} (Score: {score:.2f})")
    print(f"  {summary}")
```

### Use Case 3: Smart Extraction with Fallback

```python
config = ExtractionConfig(
    use_auto_strategy=True,
    enable_gemini=True,
    gemini_fallback_on_error=True,
    complexity_threshold=0.7
)

extractor = ConfigurableExtractor(config)

# Automatically tries openpyxl first, falls back to Gemini if needed
workbook = await extractor.extract_workbook(...)
```

### Use Case 4: Explicit Strategy Selection

```python
# Force use of Gemini for a specific file
workbook = await extractor.extract_workbook(
    file_content=file_bytes,
    file_id="123",
    file_name="complex.xlsx",
    file_path="/complex.xlsx",
    modified_time=datetime.now(),
    strategy=ExtractionStrategy.GEMINI  # Override default
)
```

## Cost Analysis

### LLM Summarization Costs

**Per File** (assuming 3 sheets average):
- Input tokens: ~300 tokens per sheet × 3 = 900 tokens
- Output tokens: ~150 tokens per sheet × 3 = 450 tokens
- Total: ~1,350 tokens per file

**With GPT-4o-mini**:
- Input: $0.150 per 1M tokens
- Output: $0.600 per 1M tokens
- Cost per file: ~$0.0004 (less than a penny)

**With GPT-4**:
- Input: $5.00 per 1M tokens
- Output: $15.00 per 1M tokens
- Cost per file: ~$0.013 (1.3 cents)

**Recommendation**: Use GPT-4o-mini for summarization (10x cheaper, good quality)

### Gemini Extraction Costs

**Per File**:
- Gemini 1.5 Flash: ~$0.05-0.10 per file
- Only used for complex files (estimated 5-10% of files)
- Average cost impact: ~$0.005-0.01 per file

## Implementation Status

### ✅ Completed

1. **LLM Summarization**:
   - SheetSummarizer class
   - Summary generation during extraction
   - Sheet ranking for queries
   - Integration with LLM service abstractions

2. **Configurable Extraction**:
   - ExtractionStrategy enum
   - ExtractionConfig model
   - ConfigurableExtractor with strategy pattern
   - Quality evaluation metrics

3. **Data Models**:
   - Updated SheetData with llm_summary fields
   - ExtractionQuality model

4. **Configuration**:
   - Environment variable support
   - Integration with main AppConfig

5. **Documentation**:
   - Usage examples
   - Configuration guide
   - Cost analysis

### 🚧 Placeholder (Future Implementation)

1. **Gemini Extractor**:
   - Placeholder class created
   - Requires google-generativeai SDK
   - Needs implementation of extraction logic

2. **LlamaParse Extractor**:
   - Placeholder class created
   - Requires llama-parse SDK
   - Needs implementation of extraction logic

## Testing

### Manual Testing

Run the example script:
```bash
python examples/configurable_extraction_usage.py
```

### Integration Testing

The ConfigurableExtractor can be tested with:
```python
import pytest
from src.extraction import ConfigurableExtractor, ExtractionConfig

@pytest.mark.asyncio
async def test_extraction_with_summarization():
    config = ExtractionConfig(enable_llm_summarization=True)
    extractor = ConfigurableExtractor(config)
    
    workbook = await extractor.extract_workbook(...)
    
    assert workbook.sheets[0].llm_summary is not None
```

## Migration Guide

### For Existing Code

**Before**:
```python
from src.extraction import ContentExtractor

extractor = ContentExtractor()
workbook = extractor.extract_workbook(...)
```

**After (with LLM summarization)**:
```python
from src.extraction import ConfigurableExtractor, ExtractionConfig

config = ExtractionConfig(enable_llm_summarization=True)
extractor = ConfigurableExtractor(config)
workbook = await extractor.extract_workbook(...)  # Now async
```

**Note**: The old `ContentExtractor` still works for backward compatibility.

## Future Enhancements

1. **Gemini Implementation**:
   - Full integration with Google Generative AI SDK
   - Multimodal understanding of visual layouts
   - Chart image analysis

2. **LlamaParse Implementation**:
   - Integration with LlamaParse API
   - Document-style Excel parsing

3. **Caching**:
   - Cache LLM summaries to avoid regeneration
   - Cache extraction results for unchanged files

4. **Batch Summarization**:
   - Batch multiple sheets in one LLM call
   - Reduce API calls and costs

5. **Custom Prompts**:
   - Allow users to customize summarization prompts
   - Domain-specific summary templates

## Troubleshooting

### LLM Summarization Not Working

**Check**:
1. `ENABLE_LLM_SUMMARIZATION=true` is set
2. LLM API key is configured (`LLM_API_KEY`)
3. LLM provider is supported (openai, anthropic, gemini)

### Gemini Fallback Not Triggering

**Check**:
1. `ENABLE_GEMINI_EXTRACTION=true` is set
2. `GEMINI_API_KEY` is configured
3. `GEMINI_FALLBACK_ON_ERROR=true` is set
4. Extraction quality is below threshold

### Async/Await Errors

The ConfigurableExtractor uses async methods. Make sure to:
```python
import asyncio

async def main():
    workbook = await extractor.extract_workbook(...)

asyncio.run(main())
```

## Conclusion

These enhancements provide a flexible, extensible extraction system that:
- Improves sheet selection accuracy with LLM summaries
- Supports multiple extraction backends
- Provides smart fallback for complex files
- Maintains backward compatibility
- Keeps costs low with efficient summarization

The system is production-ready for openpyxl + LLM summarization, with placeholders for future Gemini and LlamaParse integration.
